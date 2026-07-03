#!/usr/bin/env python3
"""Serve the YOLO annotator with reliable local label writes."""

from __future__ import annotations

import argparse
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .dataset import (
    IMAGE_SUFFIXES,
    iter_image_paths,
    label_path_for_image,
    normalize_dataset_rel_path,
    read_excluded_paths,
    safe_relative_path,
)
from .paths import DEFAULT_EXCLUDED_FILE, DEFAULT_IMAGES_ROOT, DEFAULT_LABELS_ROOT, TOOL_ROOT

FRAME_NAME_RE = re.compile(r"^(?P<video>.+)_(?P<camera>cam\d+)_frame_(?P<frame>\d+)$")
DEFAULT_INDEX_FILE = TOOL_ROOT / "web" / "yolo-annotator" / "index.html"


class LabelPayload(BaseModel):
    text: str = ""


class ExcludedPayload(BaseModel):
    excluded: bool


@dataclass(frozen=True)
class ImageRecord:
    path: str
    video: str
    camera: str
    frame: int | None


LabelStatus = str


def parse_image_path(image_path: str) -> ImageRecord:
    rel_path = PurePosixPath(image_path)
    match = FRAME_NAME_RE.match(rel_path.stem)
    if match:
        return ImageRecord(
            path=image_path,
            video=match.group("video"),
            camera=match.group("camera"),
            frame=int(match.group("frame")),
        )

    parts = rel_path.parts
    camera = parts[0] if parts else "default"
    video = rel_path.parent.as_posix() if rel_path.parent.as_posix() != "." else rel_path.stem
    return ImageRecord(path=image_path, video=video, camera=camera, frame=None)


def label_status_from_text(text: str) -> LabelStatus:
    return "ball" if text.strip() else "empty"


def label_status_for_path(path: Path) -> LabelStatus:
    if not path.is_file():
        return "unlabeled"
    return label_status_from_text(path.read_text(encoding="utf-8"))


def write_excluded_paths(path: Path, excluded: set[str]) -> None:
    text = "".join(f"{item}\n" for item in sorted(excluded))
    atomic_write_text(path, text)


def image_record_sort_key(record: ImageRecord) -> tuple[str, str, int, str]:
    frame = record.frame if record.frame is not None else 10**12
    return (record.video, record.camera, frame, record.path)


def image_entries(
    images_root: Path,
    labels_root: Path,
    excluded_file: Path | None = None,
) -> list[dict[str, str | int | bool | None]]:
    records = [parse_image_path(path) for path in iter_image_paths(images_root)]
    excluded_paths = read_excluded_paths(excluded_file)
    entries = []
    for record in sorted(records, key=image_record_sort_key):
        label_status = label_status_for_path(label_path_for_image(labels_root, record.path))
        entries.append(
            {
                "path": record.path,
                "video": record.video,
                "camera": record.camera,
                "frame": record.frame,
                "label_exists": label_status != "unlabeled",
                "label_status": label_status,
                "excluded": record.path in excluded_paths,
            }
        )
    return entries


def build_video_summaries(
    images_root: Path,
    labels_root: Path,
    excluded_file: Path | None = None,
) -> list[dict[str, object]]:
    videos: dict[str, dict[str, object]] = {}
    for entry in image_entries(images_root, labels_root, excluded_file):
        video_id = str(entry["video"])
        camera = str(entry["camera"])
        video = videos.setdefault(
            video_id,
            {
                "id": video_id,
                "total": 0,
                "labeled": 0,
                "unlabeled": 0,
                "empty": 0,
                "ball": 0,
                "excluded": 0,
                "cameras": {},
            },
        )
        cameras = video["cameras"]
        assert isinstance(cameras, dict)
        stats = cameras.setdefault(
            camera,
            {
                "total": 0,
                "labeled": 0,
                "unlabeled": 0,
                "empty": 0,
                "ball": 0,
                "excluded": 0,
                "first_image": entry["path"],
            },
        )
        assert isinstance(stats, dict)
        label_status = str(entry["label_status"])
        stats["total"] = int(stats["total"]) + 1
        video["total"] = int(video["total"]) + 1
        if bool(entry.get("excluded")):
            stats["excluded"] = int(stats["excluded"]) + 1
            video["excluded"] = int(video["excluded"]) + 1
        if label_status == "unlabeled":
            stats["unlabeled"] = int(stats["unlabeled"]) + 1
            video["unlabeled"] = int(video["unlabeled"]) + 1
        else:
            stats["labeled"] = int(stats["labeled"]) + 1
            video["labeled"] = int(video["labeled"]) + 1
            if label_status == "empty":
                stats["empty"] = int(stats["empty"]) + 1
                video["empty"] = int(video["empty"]) + 1
            elif label_status == "ball":
                stats["ball"] = int(stats["ball"]) + 1
                video["ball"] = int(video["ball"]) + 1
    return [videos[key] for key in sorted(videos)]


def atomic_write_text(path: Path, text: str) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        fsync_directory(path.parent)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    return len(text.encode("utf-8"))


def fsync_directory(path: Path) -> None:
    open_flags = getattr(os, "O_DIRECTORY", 0) | os.O_RDONLY
    try:
        fd = os.open(path, open_flags)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def create_app(
    images_root: Path = DEFAULT_IMAGES_ROOT,
    labels_root: Path = DEFAULT_LABELS_ROOT,
    index_file: Path = DEFAULT_INDEX_FILE,
    excluded_file: Path = DEFAULT_EXCLUDED_FILE,
) -> FastAPI:
    images_root = images_root.resolve()
    labels_root = labels_root.resolve()
    index_file = index_file.resolve()
    excluded_file = excluded_file.resolve()
    app = FastAPI(title="Tennis Ball YOLO Annotator")

    @app.get("/")
    async def index() -> FileResponse:
        if not index_file.exists():
            raise HTTPException(status_code=404, detail="annotator index.html not found")
        return FileResponse(index_file, media_type="text/html")

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {
            "images_root": images_root.as_posix(),
            "labels_root": labels_root.as_posix(),
            "excluded_file": excluded_file.as_posix(),
        }

    @app.get("/api/videos")
    async def list_videos() -> dict[str, list[dict[str, object]]]:
        return {"videos": build_video_summaries(images_root, labels_root, excluded_file)}

    @app.get("/api/images")
    async def list_images(video: str | None = None, camera: str | None = None) -> dict[str, list[dict[str, object]]]:
        entries = image_entries(images_root, labels_root, excluded_file)
        if video:
            entries = [entry for entry in entries if entry["video"] == video]
        if camera:
            entries = [entry for entry in entries if entry["camera"] == camera]
        return {"images": entries}

    @app.get("/api/images/{image_path:path}")
    async def get_image(image_path: str) -> FileResponse:
        try:
            path = safe_relative_path(images_root, image_path, IMAGE_SUFFIXES)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not path.is_file():
            raise HTTPException(status_code=404, detail="image not found")
        return FileResponse(path)

    @app.get("/api/labels/{label_path:path}")
    async def get_label(label_path: str) -> dict[str, str]:
        try:
            path = safe_relative_path(labels_root, label_path, {".txt"})
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not path.exists():
            return {"path": label_path, "text": ""}
        if not path.is_file():
            raise HTTPException(status_code=404, detail="label path is not a file")
        return {"path": label_path, "text": path.read_text(encoding="utf-8")}

    @app.put("/api/labels/{label_path:path}")
    async def put_label(label_path: str, payload: LabelPayload) -> dict[str, str | int | bool]:
        try:
            path = safe_relative_path(labels_root, label_path, {".txt"})
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        previous_status = label_status_for_path(path)
        created = previous_status == "unlabeled"
        byte_count = atomic_write_text(path, payload.text)
        return {
            "ok": True,
            "path": label_path,
            "bytes": byte_count,
            "created": created,
            "previous_status": previous_status,
            "label_status": label_status_from_text(payload.text),
        }

    @app.put("/api/excluded/{image_path:path}")
    async def put_excluded(image_path: str, payload: ExcludedPayload) -> dict[str, str | bool]:
        try:
            path = safe_relative_path(images_root, image_path, IMAGE_SUFFIXES)
            normalized = normalize_dataset_rel_path(image_path)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not path.is_file():
            raise HTTPException(status_code=404, detail="image not found")

        excluded = read_excluded_paths(excluded_file)
        previous = normalized in excluded
        if payload.excluded:
            excluded.add(normalized)
        else:
            excluded.discard(normalized)
        write_excluded_paths(excluded_file, excluded)
        return {
            "ok": True,
            "path": normalized,
            "previous_excluded": previous,
            "excluded": normalized in excluded,
        }

    return app


def serve_annotator(
    *,
    images_root: Path = DEFAULT_IMAGES_ROOT,
    labels_root: Path = DEFAULT_LABELS_ROOT,
    excluded_file: Path = DEFAULT_EXCLUDED_FILE,
    index_file: Path = DEFAULT_INDEX_FILE,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> None:
    app = create_app(images_root, labels_root, index_file, excluded_file)
    uvicorn.run(app, host=host, port=port)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve the local YOLO annotation backend.")
    parser.add_argument("--images", type=Path, default=DEFAULT_IMAGES_ROOT, help="image root directory")
    parser.add_argument("--labels", type=Path, default=DEFAULT_LABELS_ROOT, help="label root directory")
    parser.add_argument("--excluded", type=Path, default=DEFAULT_EXCLUDED_FILE, help="excluded image list")
    parser.add_argument("--host", default="127.0.0.1", help="server host")
    parser.add_argument("--port", type=int, default=8765, help="server port")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    serve_annotator(images_root=args.images, labels_root=args.labels, excluded_file=args.excluded, host=args.host, port=args.port)


if __name__ == "__main__":
    main()

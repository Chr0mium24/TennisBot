from __future__ import annotations

import argparse
import json
import math
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .dataset import (
    IMAGE_SUFFIXES,
    iter_image_paths,
    label_path_for_image,
    read_excluded_paths,
    read_yolo_labels,
    safe_relative_path,
    yolo_to_pixel_box,
)
from .io import write_json
from .paths import DEFAULT_DATASET_ROOT, DEFAULT_EXCLUDED_FILE, DEFAULT_IMAGES_ROOT, DEFAULT_LABELS_ROOT, DEFAULT_SPRITES_ROOT, TOOL_ROOT


DEFAULT_REVIEW_INDEX = TOOL_ROOT / "web" / "yolo-sprite-review" / "index.html"
SAFE_ID_RE = re.compile(r"[^A-Za-z0-9_.-]+")


class MaskPayload(BaseModel):
    center_x: float
    center_y: float
    radius_x: float
    radius_y: float
    rotation_deg: float = 0.0
    feather_px: int = 4


@dataclass(frozen=True)
class SpriteExtractionResult:
    candidates: int
    skipped_images: int
    output_root: Path
    manifest: Path


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def require_cv2_numpy() -> tuple[Any, Any]:
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise RuntimeError(
            "opencv-python and numpy are required for sprite/augmentation commands. "
            "Run through `uv run --extra augment tennisbot-yolo ...`."
        ) from exc
    return cv2, np


def sprite_id_for(image_rel_path: str, box_index: int) -> str:
    stem = Path(image_rel_path).with_suffix("").as_posix()
    safe = SAFE_ID_RE.sub("_", stem).strip("._")
    return f"{safe or 'image'}__box{box_index:02d}"


def ellipse_alpha_mask(
    height: int,
    width: int,
    *,
    center_x: float,
    center_y: float,
    radius_x: float,
    radius_y: float,
    rotation_deg: float = 0.0,
    feather_px: int = 4,
) -> Any:
    cv2, np = require_cv2_numpy()
    mask = np.zeros((height, width), dtype=np.uint8)
    radius_x = max(1.0, float(radius_x))
    radius_y = max(1.0, float(radius_y))
    cv2.ellipse(
        mask,
        (int(round(center_x)), int(round(center_y))),
        (int(round(radius_x)), int(round(radius_y))),
        float(rotation_deg),
        0,
        360,
        255,
        thickness=-1,
        lineType=cv2.LINE_AA,
    )
    feather_px = max(0, int(feather_px))
    if feather_px > 0:
        kernel = feather_px * 2 + 1
        mask = cv2.GaussianBlur(mask, (kernel, kernel), 0)
    return mask


def write_sprite_png(source_bgr: Any, alpha: Any, output_path: Path) -> None:
    cv2, np = require_cv2_numpy()
    if source_bgr.shape[:2] != alpha.shape[:2]:
        raise ValueError("source image and alpha mask dimensions differ")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    bgra = np.dstack([source_bgr[:, :, 0], source_bgr[:, :, 1], source_bgr[:, :, 2], alpha])
    if not cv2.imwrite(str(output_path), bgra):
        raise RuntimeError(f"could not write sprite: {output_path}")


def write_crop_preview(source_bgr: Any, output_path: Path, jpeg_quality: int = 92) -> None:
    cv2, _ = require_cv2_numpy()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    params = [int(cv2.IMWRITE_JPEG_QUALITY), max(1, min(100, int(jpeg_quality)))]
    if not cv2.imwrite(str(output_path), source_bgr, params):
        raise RuntimeError(f"could not write crop preview: {output_path}")


def extract_sprites(
    *,
    images_root: Path = DEFAULT_IMAGES_ROOT,
    labels_root: Path = DEFAULT_LABELS_ROOT,
    excluded_file: Path = DEFAULT_EXCLUDED_FILE,
    output_root: Path = DEFAULT_SPRITES_ROOT,
    class_id: int = 0,
    padding_scale: float = 0.35,
    feather_px: int = 4,
    limit: int | None = None,
    overwrite: bool = False,
) -> SpriteExtractionResult:
    cv2, _ = require_cv2_numpy()
    images_root = images_root.resolve()
    labels_root = labels_root.resolve()
    excluded_paths = read_excluded_paths(excluded_file)
    candidates_dir = output_root.resolve() / "candidates"
    manifest_path = output_root.resolve() / "manifest.jsonl"
    candidates_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    generated = 0
    skipped_images = 0
    manifest_rows: list[dict[str, Any]] = []
    for image_rel_path in iter_image_paths(images_root):
        if limit is not None and generated >= limit:
            break
        if image_rel_path in excluded_paths:
            skipped_images += 1
            continue
        label_path = label_path_for_image(labels_root, image_rel_path)
        labels = [label for label in read_yolo_labels(label_path) if label.class_id == class_id]
        if not labels:
            skipped_images += 1
            continue
        image_path = safe_relative_path(images_root, image_rel_path, IMAGE_SUFFIXES)
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            skipped_images += 1
            continue
        image_height, image_width = image.shape[:2]

        for box_index, label in enumerate(labels):
            if limit is not None and generated >= limit:
                break
            bbox = yolo_to_pixel_box(label, image_width, image_height)
            if bbox.width <= 1 or bbox.height <= 1:
                continue
            candidate_id = sprite_id_for(image_rel_path, box_index)
            sprite_path = candidates_dir / f"{candidate_id}.png"
            crop_path = candidates_dir / f"{candidate_id}_crop.jpg"
            metadata_path = candidates_dir / f"{candidate_id}.json"
            if metadata_path.exists() and not overwrite:
                generated += 1
                continue

            pad = max(bbox.width, bbox.height) * max(0.0, padding_scale)
            x1 = max(0, int(math.floor(bbox.x1 - pad)))
            y1 = max(0, int(math.floor(bbox.y1 - pad)))
            x2 = min(image_width, int(math.ceil(bbox.x2 + pad)))
            y2 = min(image_height, int(math.ceil(bbox.y2 + pad)))
            crop = image[y1:y2, x1:x2]
            if crop.size == 0:
                continue

            mask_payload = {
                "center_x": bbox.x_center - x1,
                "center_y": bbox.y_center - y1,
                "radius_x": max(1.0, bbox.width * 0.5),
                "radius_y": max(1.0, bbox.height * 0.5),
                "rotation_deg": 0.0,
                "feather_px": max(0, int(feather_px)),
            }
            alpha = ellipse_alpha_mask(crop.shape[0], crop.shape[1], **mask_payload)
            write_sprite_png(crop, alpha, sprite_path)
            write_crop_preview(crop, crop_path)

            metadata = {
                "id": candidate_id,
                "status": "candidate",
                "created_at": utc_now_iso(),
                "updated_at": utc_now_iso(),
                "source": {
                    "images_root": images_root.as_posix(),
                    "labels_root": labels_root.as_posix(),
                    "image": image_rel_path,
                    "label": label_path.relative_to(labels_root).as_posix(),
                    "line_index": box_index,
                    "image_size": {"width": image_width, "height": image_height},
                    "bbox_px": {"x1": bbox.x1, "y1": bbox.y1, "x2": bbox.x2, "y2": bbox.y2},
                    "bbox_yolo": {
                        "class_id": label.class_id,
                        "x_center": label.x_center,
                        "y_center": label.y_center,
                        "width": label.width,
                        "height": label.height,
                    },
                },
                "crop": {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "width": x2 - x1, "height": y2 - y1},
                "mask": mask_payload,
                "files": {"sprite": sprite_path.name, "crop": crop_path.name, "metadata": metadata_path.name},
            }
            write_json(metadata_path, metadata)
            manifest_rows.append(metadata)
            generated += 1

    manifest_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in manifest_rows), encoding="utf-8")
    return SpriteExtractionResult(
        candidates=generated,
        skipped_images=skipped_images,
        output_root=output_root.resolve(),
        manifest=manifest_path,
    )


def load_sprite_metadata(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def candidate_metadata_path(sprites_root: Path, sprite_id: str) -> Path:
    if SAFE_ID_RE.search(sprite_id) or not sprite_id:
        raise ValueError("unsafe sprite id")
    return sprites_root.resolve() / "candidates" / f"{sprite_id}.json"


def regenerate_sprite_from_metadata(metadata: dict[str, Any], metadata_path: Path) -> None:
    cv2, _ = require_cv2_numpy()
    source = metadata["source"]
    crop = metadata["crop"]
    mask = metadata["mask"]
    image_path = safe_relative_path(Path(source["images_root"]), source["image"], IMAGE_SUFFIXES)
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"could not read source image: {image_path}")
    crop_bgr = image[int(crop["y1"]) : int(crop["y2"]), int(crop["x1"]) : int(crop["x2"])]
    alpha = ellipse_alpha_mask(crop_bgr.shape[0], crop_bgr.shape[1], **mask)
    base_dir = metadata_path.parent
    write_sprite_png(crop_bgr, alpha, base_dir / metadata["files"]["sprite"])
    write_crop_preview(crop_bgr, base_dir / metadata["files"]["crop"])


def copy_reviewed_sprite(sprites_root: Path, metadata: dict[str, Any], metadata_path: Path, status: str) -> None:
    if status not in {"approved", "rejected"}:
        raise ValueError(f"unsupported review status: {status}")
    target_dir = sprites_root.resolve() / status
    target_dir.mkdir(parents=True, exist_ok=True)
    metadata["status"] = status
    metadata["updated_at"] = utc_now_iso()
    write_json(metadata_path, metadata)
    sprite_name = metadata["files"]["sprite"]
    crop_name = metadata["files"]["crop"]
    shutil.copy2(metadata_path.parent / sprite_name, target_dir / sprite_name)
    shutil.copy2(metadata_path.parent / crop_name, target_dir / crop_name)
    write_json(target_dir / metadata["files"]["metadata"], metadata)


def list_candidate_metadata(sprites_root: Path) -> list[dict[str, Any]]:
    candidates_dir = sprites_root.resolve() / "candidates"
    if not candidates_dir.exists():
        return []
    items = []
    for path in sorted(candidates_dir.glob("*.json")):
        metadata = load_sprite_metadata(path)
        metadata["urls"] = {
            "sprite": f"/api/assets/candidates/{metadata['files']['sprite']}",
            "crop": f"/api/assets/candidates/{metadata['files']['crop']}",
        }
        items.append(metadata)
    return items


def update_sprite_mask(sprites_root: Path, sprite_id: str, payload: MaskPayload) -> dict[str, Any]:
    metadata_path = candidate_metadata_path(sprites_root, sprite_id)
    if not metadata_path.is_file():
        raise FileNotFoundError(metadata_path)
    metadata = load_sprite_metadata(metadata_path)
    crop = metadata["crop"]
    mask = payload.model_dump()
    if not 0 <= mask["center_x"] <= crop["width"] or not 0 <= mask["center_y"] <= crop["height"]:
        raise ValueError("mask center must stay inside the crop")
    if mask["radius_x"] <= 0 or mask["radius_y"] <= 0:
        raise ValueError("mask radii must be positive")
    if mask["feather_px"] < 0:
        raise ValueError("mask feather must be non-negative")
    metadata["mask"] = mask
    metadata["updated_at"] = utc_now_iso()
    write_json(metadata_path, metadata)
    regenerate_sprite_from_metadata(metadata, metadata_path)
    return metadata


def create_review_app(sprites_root: Path = DEFAULT_SPRITES_ROOT, index_file: Path = DEFAULT_REVIEW_INDEX) -> FastAPI:
    sprites_root = sprites_root.resolve()
    index_file = index_file.resolve()
    app = FastAPI(title="TennisBot YOLO Sprite Review")

    @app.get("/")
    async def index() -> FileResponse:
        if not index_file.is_file():
            raise HTTPException(status_code=404, detail="sprite review index.html not found")
        return FileResponse(index_file, media_type="text/html")

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"sprites_root": sprites_root.as_posix()}

    @app.get("/api/sprites")
    async def sprites() -> dict[str, list[dict[str, Any]]]:
        return {"sprites": list_candidate_metadata(sprites_root)}

    @app.get("/api/sprites/{sprite_id}")
    async def sprite(sprite_id: str) -> dict[str, Any]:
        try:
            path = candidate_metadata_path(sprites_root, sprite_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not path.is_file():
            raise HTTPException(status_code=404, detail="sprite not found")
        metadata = load_sprite_metadata(path)
        metadata["urls"] = {
            "sprite": f"/api/assets/candidates/{metadata['files']['sprite']}",
            "crop": f"/api/assets/candidates/{metadata['files']['crop']}",
        }
        return metadata

    @app.post("/api/sprites/{sprite_id}/mask")
    async def save_mask(sprite_id: str, payload: MaskPayload) -> dict[str, Any]:
        try:
            metadata = update_sprite_mask(sprites_root, sprite_id, payload)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="sprite not found") from exc
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        metadata["urls"] = {
            "sprite": f"/api/assets/candidates/{metadata['files']['sprite']}",
            "crop": f"/api/assets/candidates/{metadata['files']['crop']}",
        }
        return {"ok": True, "sprite": metadata}

    @app.post("/api/sprites/{sprite_id}/approve")
    async def approve(sprite_id: str) -> dict[str, Any]:
        return _review(sprite_id, "approved")

    @app.post("/api/sprites/{sprite_id}/reject")
    async def reject(sprite_id: str) -> dict[str, Any]:
        return _review(sprite_id, "rejected")

    def _review(sprite_id: str, status: str) -> dict[str, Any]:
        try:
            path = candidate_metadata_path(sprites_root, sprite_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not path.is_file():
            raise HTTPException(status_code=404, detail="sprite not found")
        metadata = load_sprite_metadata(path)
        copy_reviewed_sprite(sprites_root, metadata, path, status)
        return {"ok": True, "status": status, "id": sprite_id}

    @app.get("/api/assets/{bucket}/{filename}")
    async def asset(bucket: str, filename: str) -> FileResponse:
        if bucket not in {"candidates", "approved", "rejected"}:
            raise HTTPException(status_code=400, detail="unsupported asset bucket")
        try:
            path = safe_relative_path(sprites_root / bucket, filename, {".png", ".jpg", ".jpeg"})
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not path.is_file():
            raise HTTPException(status_code=404, detail="asset not found")
        media_type = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
        return FileResponse(path, media_type=media_type)

    return app


def cmd_extract_sprites(args: argparse.Namespace) -> int:
    try:
        result = extract_sprites(
            images_root=args.images_root,
            labels_root=args.labels_root,
            excluded_file=args.excluded_file,
            output_root=args.output_root,
            class_id=args.class_id,
            padding_scale=args.padding_scale,
            feather_px=args.feather_px,
            limit=args.limit,
            overwrite=args.overwrite,
        )
    except (RuntimeError, ValueError, FileNotFoundError) as exc:
        print(f"error: {exc}")
        return 2
    print(f"candidates={result.candidates}")
    print(f"skipped_images={result.skipped_images}")
    print(f"output_root={result.output_root}")
    print(f"manifest={result.manifest}")
    return 0


def add_sprites_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser_kwargs = {"formatter_class": argparse.ArgumentDefaultsHelpFormatter}
    sprites = subparsers.add_parser("sprites", help="提取和审核网球 sprite。", **parser_kwargs)
    sprite_subparsers = sprites.add_subparsers(dest="sprites_command", required=True)

    extract = sprite_subparsers.add_parser("extract", help="从 YOLO bbox 标签提取候选球 sprite。", **parser_kwargs)
    extract.add_argument("--images-root", type=Path, default=DEFAULT_IMAGES_ROOT, help="图片根目录")
    extract.add_argument("--labels-root", type=Path, default=DEFAULT_LABELS_ROOT, help="YOLO 标签根目录")
    extract.add_argument("--excluded-file", type=Path, default=DEFAULT_EXCLUDED_FILE, help="排除图片列表")
    extract.add_argument("--output-root", type=Path, default=DEFAULT_SPRITES_ROOT, help="sprite 输出根目录")
    extract.add_argument("--class-id", type=int, default=0, help="要提取的 YOLO 类别 id")
    extract.add_argument("--padding-scale", type=float, default=0.35, help="bbox 外扩比例")
    extract.add_argument("--feather-px", type=int, default=4, help="alpha mask 边缘羽化像素")
    extract.add_argument("--limit", type=int, help="最多提取的候选数量")
    extract.add_argument("--overwrite", action="store_true", help="覆盖已存在的候选")
    extract.set_defaults(func=cmd_extract_sprites)

    review = sprite_subparsers.add_parser("review", help="启动本机球 sprite 审核页面。", **parser_kwargs)
    review.add_argument("--sprites-root", type=Path, default=DEFAULT_SPRITES_ROOT, help="sprite 输出根目录")
    review.add_argument("--host", default="127.0.0.1", help="HTTP 监听地址")
    review.add_argument("--port", type=int, default=8766, help="HTTP 监听端口")
    review.set_defaults(func=cmd_review_sprites)


def cmd_review_sprites(args: argparse.Namespace) -> int:
    import uvicorn

    app = create_review_app(args.sprites_root, DEFAULT_REVIEW_INDEX)
    uvicorn.run(app, host=args.host, port=args.port)
    return 0

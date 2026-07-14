from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Sequence

from .config import REPO_ROOT, safe_label
from .recording import display_command


VIDEO_SUFFIXES = {".mkv", ".mp4", ".avi", ".mov"}


@dataclass(frozen=True)
class ExtractOptions:
    inputs: list[str]
    fps: float
    dataset_root: Path
    images_dir: Path | None
    labels_dir: Path | None
    recordings_root: Path
    session: str
    image_format: str
    jpeg_quality: int
    png_compression: int
    cam_map: str
    overwrite: bool
    dry_run: bool


@dataclass(frozen=True)
class NormalizeOptions:
    inputs: list[str]
    output_dir: Path | None
    suffix: str
    base_epoch: str
    overwrite: bool
    dry_run: bool


@dataclass(frozen=True)
class InputGroup:
    label: str
    session_hint: str
    videos: list[Path]
    output_dir: Path | None = None


def extract_yolo_frames(options: ExtractOptions) -> int:
    image_format = normalize_image_format(options.image_format)
    images_dir = repo_relative(options.images_dir) if options.images_dir is not None else repo_relative(options.dataset_root) / "images"
    labels_dir = repo_relative(options.labels_dir) if options.labels_dir is not None else repo_relative(options.dataset_root) / "labels"
    groups = collect_input_groups(options.inputs, repo_relative(options.recordings_root))
    if not groups:
        raise ValueError("No video files found.")
    if options.session and len(groups) > 1:
        raise ValueError("--session can only be used with one input group")
    cam_map = parse_cam_map(options.cam_map)
    processed = 0
    for group in groups:
        if not group.videos:
            print(f"No video files found in {group.label}.")
            continue
        processed += len(group.videos)
        session = safe_label(options.session or group.session_hint or infer_session(group.videos[0]))
        labels = [camera_label_for_file(video, cam_map) for video in group.videos]
        if len(set(labels)) != len(labels):
            raise ValueError(f"Multiple videos in {group.label} map to the same camera; adjust --cam-map")
        if not options.dry_run:
            images_dir.mkdir(parents=True, exist_ok=True)
            labels_dir.mkdir(parents=True, exist_ok=True)
        print("")
        print(f"Group: {group.label}")
        print(f"Session: {session}")
        print(f"FPS: {options.fps:g}")
        print(f"Images: {images_dir}")
        print(f"Labels: {labels_dir}")
        for video, camera in zip(group.videos, labels, strict=True):
            pattern = images_dir / f"{session}_{camera}_frame_%06d.{image_format}"
            command = build_extract_command(
                video,
                pattern,
                fps=options.fps,
                image_format=image_format,
                jpeg_quality=options.jpeg_quality,
                png_compression=options.png_compression,
                overwrite=options.overwrite,
            )
            print("")
            print(f"Extracting {video} -> {pattern}")
            if options.dry_run:
                print(display_command(command))
                continue
            ensure_no_existing_frames(images_dir, session, camera, image_format, overwrite=options.overwrite)
            subprocess.run(command, check=True)
    if processed == 0:
        raise ValueError("No video files found.")
    print("")
    print("Done. Start the annotation service and open http://127.0.0.1:8765")
    return 0


def normalize_timestamps(options: NormalizeOptions) -> int:
    groups = collect_normalize_groups(options.inputs, repo_relative_optional(options.output_dir), options.suffix)
    if not groups:
        raise ValueError("No video files found.")
    for group in groups:
        if not group.videos:
            print(f"No video files found in {group.label}.")
            continue
        base_epoch = options.base_epoch or earliest_first_pts(group.videos)
        if group.output_dir is not None and not options.dry_run:
            group.output_dir.mkdir(parents=True, exist_ok=True)
        print("")
        print(f"Group: {group.label}")
        print(f"Subtracting timestamp base: {base_epoch}")
        for video in group.videos:
            output = normalize_output_path(video, group.output_dir, options.suffix)
            if output == video:
                raise ValueError(f"Output path would overwrite input: {video}")
            command = build_normalize_command(
                video,
                output,
                base_epoch=base_epoch,
                overwrite=options.overwrite,
            )
            print("")
            print(f"Normalizing {video} -> {output}")
            if options.dry_run:
                print(display_command(command))
                continue
            if output.exists() and not options.overwrite:
                raise FileExistsError(f"Output already exists: {output}. Use --overwrite to replace it.")
            subprocess.run(command, check=True)
    print("")
    print("Done.")
    return 0


def build_extract_command(
    video: Path,
    pattern: Path,
    *,
    fps: float,
    image_format: str,
    jpeg_quality: int,
    png_compression: int,
    overwrite: bool,
) -> list[str]:
    command = ["ffmpeg", "-hide_banner", "-loglevel", "info", "-y" if overwrite else "-n"]
    command.extend(["-i", str(video), "-vf", f"fps={fps:g}", "-start_number", "1"])
    if image_format == "jpg":
        command.extend(["-q:v", str(jpeg_quality), str(pattern)])
    else:
        command.extend(["-compression_level", str(png_compression), str(pattern)])
    return command


def build_normalize_command(video: Path, output: Path, *, base_epoch: str, overwrite: bool) -> list[str]:
    return [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "info",
        "-y" if overwrite else "-n",
        "-copyts",
        "-i",
        str(video),
        "-map",
        "0",
        "-c",
        "copy",
        "-output_ts_offset",
        f"-{base_epoch}",
        "-metadata",
        f"soft_sync_base_epoch={base_epoch}",
        "-metadata",
        f"normalized_from={video.name}",
        "-f",
        "matroska",
        str(output),
    ]


def collect_input_groups(inputs: Sequence[str], recordings_root: Path) -> list[InputGroup]:
    dirs: list[Path] = []
    files: list[Path] = []
    for raw in inputs:
        candidate = repo_relative(Path(raw))
        if candidate.is_dir():
            dirs.append(candidate)
        elif candidate.is_file():
            if not is_video_file(candidate):
                raise ValueError(f"Not a supported video file: {candidate}")
            files.append(candidate)
        else:
            session_dir = recordings_root / raw
            if session_dir.is_dir():
                dirs.append(session_dir)
            else:
                raise FileNotFoundError(f"Input not found: {raw}")
    groups = [InputGroup(label=str(directory), session_hint=directory.name, videos=find_videos(directory)) for directory in dirs]
    if files:
        groups.append(InputGroup(label="explicit files", session_hint="", videos=files))
    return groups


def collect_normalize_groups(inputs: Sequence[str], output_dir: Path | None, suffix: str) -> list[InputGroup]:
    dirs: list[Path] = []
    files: list[Path] = []
    for raw in inputs:
        candidate = repo_relative(Path(raw))
        if candidate.is_dir():
            dirs.append(candidate)
        elif candidate.is_file():
            if not is_video_file(candidate):
                raise ValueError(f"Not a supported video file: {candidate}")
            files.append(candidate)
        else:
            raise FileNotFoundError(f"Input not found: {raw}")
    group_count = len(dirs) + (1 if files else 0)
    groups: list[InputGroup] = []
    for directory in dirs:
        group_output = None
        if output_dir is not None:
            group_output = output_dir / directory.name if group_count > 1 else output_dir
        groups.append(InputGroup(label=str(directory), session_hint=directory.name, videos=find_videos(directory, skip_suffix=suffix), output_dir=group_output))
    if files:
        group_output = output_dir / "files" if output_dir is not None and group_count > 1 else output_dir
        groups.append(InputGroup(label="explicit files", session_hint="", videos=files, output_dir=group_output))
    return groups


def find_videos(directory: Path, *, skip_suffix: str = "") -> list[Path]:
    videos = [path for path in directory.rglob("*") if path.is_file() and is_video_file(path)]
    if skip_suffix:
        videos = [path for path in videos if not path.name.endswith(f"{skip_suffix}.mkv")]
    return sorted(videos)


def parse_cam_map(value: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for entry in value.split(","):
        if ":" not in entry:
            raise ValueError(f"Invalid camera map entry: {entry}")
        source, target = entry.split(":", 1)
        if not source or not target:
            raise ValueError(f"Invalid camera map entry: {entry}")
        mapping[source] = safe_label(target)
    if not mapping:
        raise ValueError("--cam-map cannot be empty")
    return mapping


def camera_label_for_file(video: Path, cam_map: dict[str, str]) -> str:
    base = video.name
    for source, target in cam_map.items():
        if source in base:
            return target
    stem = video.stem
    for token in stem.split("_"):
        if token.startswith("cam"):
            return safe_label(token)
    return safe_label(stem)


def ensure_no_existing_frames(images_dir: Path, session: str, camera: str, image_format: str, *, overwrite: bool) -> None:
    matching = list(images_dir.glob(f"{session}_{camera}_frame_*.{image_format}"))
    if overwrite:
        for frame in matching:
            frame.unlink()
        return
    if matching:
        raise FileExistsError(f"Output already exists for {session}/{camera}: {matching[0]}. Use --overwrite.")


def earliest_first_pts(videos: Sequence[Path]) -> str:
    values = [first_video_pts(video) for video in videos]
    return min(values, key=float)


def first_video_pts(video: Path) -> str:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "packet=pts_time",
            "-of",
            "csv=p=0",
            "-read_intervals",
            "%+#1",
            str(video),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    value = result.stdout.strip().splitlines()[0]
    float(value)
    return value


def normalize_output_path(video: Path, output_dir: Path | None, suffix: str) -> Path:
    if output_dir is not None:
        return output_dir / f"{video.stem}{suffix}.mkv"
    return video.with_name(f"{video.stem}{suffix}.mkv")


def infer_session(video: Path) -> str:
    name = video.name
    if len(name) >= 15 and name[8] == "_" and name[:8].isdigit() and name[9:15].isdigit():
        return name[:15]
    return video.parent.name


def normalize_image_format(value: str) -> str:
    if value in {"jpg", "jpeg"}:
        return "jpg"
    if value == "png":
        return "png"
    raise ValueError("--format must be jpg or png")


def is_video_file(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_SUFFIXES


def repo_relative(path: Path | str) -> Path:
    path = Path(path).expanduser()
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def repo_relative_optional(path: Path | None) -> Path | None:
    if path is None:
        return None
    return repo_relative(path)

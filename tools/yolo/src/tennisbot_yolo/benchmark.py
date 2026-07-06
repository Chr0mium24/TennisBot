from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
from glob import glob
from pathlib import Path
import re
import statistics
import time
from typing import Any

from .paths import REPO_ROOT
from .roi_tracking import CropWindow, RoiTrackConfig, StatefulRoiTracker


DEFAULT_MODEL = REPO_ROOT / "artifacts" / "models" / "tennis_ball_yolo" / "model.pt"
DEFAULT_TILE_PROFILES = (
    "full_4k:3840:2160:0",
    "tile_2048x1216:2048:1216:160",
    "tile_2048x1152:2048:1152:160",
    "tile_1536x864:1536:864:160",
)
DEFAULT_IMGSZ_VALUES = "960,1280,1536"
DEFAULT_ROI_SAMPLE_LIST = (
    REPO_ROOT / "tools" / "yolo" / "workspace" / "runs" / "copy_paste_aug_1000_trial_20260703" / "val.txt"
)
DEFAULT_ROI_PROFILES = (
    "roi_960x540_512:960:540:512",
    "roi_1280x720_512:1280:720:512",
    "roi_1536x864_512:1536:864:512",
    "roi_1536x864_640:1536:864:640",
)
DEFAULT_ROI_TRACK_GLOB = (
    REPO_ROOT / "tools" / "yolo" / "workspace" / "dataset" / "images" / "0260701" / "20260701_154019_cam1_frame_*.jpg"
)
DEFAULT_S3D_CHECKPOINT = (
    REPO_ROOT
    / "tools"
    / "yolo"
    / "workspace"
    / "runs"
    / "temporal_heatmap"
    / "search_s3d_temporal_heatmap_w5_960x540_pseudo989_synth500_20260705"
    / "best_recall.pt"
)
DEFAULT_S3D_ROI_GLOB = (
    REPO_ROOT / "tools" / "yolo" / "workspace" / "dataset" / "images" / "0260701" / "20260701_155008_cam*_frame_*.jpg"
)
FRAME_NUMBER_RE = re.compile(r"_frame_(?P<frame>\d+)$")


@dataclass(frozen=True)
class TileProfile:
    name: str
    tile_width: int
    tile_height: int
    overlap: int


@dataclass(frozen=True)
class BenchmarkCase:
    profile: TileProfile
    imgsz: int


@dataclass(frozen=True)
class DryRunRow:
    case: BenchmarkCase
    x_tiles: int
    y_tiles: int
    tiles_per_camera: int
    sources_per_stereo: int
    model_input_mpix: float
    crop_mpix: float


@dataclass(frozen=True)
class TimedRow:
    dry: DryRunRow
    mean_ms: float
    median_ms: float
    p95_ms: float
    min_ms: float
    max_ms: float
    fps: float
    peak_cuda_mb: float | None
    error: str | None = None


@dataclass(frozen=True)
class RoiProfile:
    name: str
    crop_width: int
    crop_height: int
    imgsz: int


@dataclass(frozen=True)
class DetBox:
    x1: float
    y1: float
    x2: float
    y2: float
    conf: float = 1.0


@dataclass(frozen=True)
class RoiSample:
    image: Path
    width: int
    height: int
    gt_boxes: tuple[DetBox, ...]


@dataclass(frozen=True)
class RoiSampleRow:
    mode: str
    profile: str
    imgsz: str
    images: int
    gt: int
    tp: int
    fp: int
    fn: int
    recall: float
    precision: float
    median_ms: float
    p95_ms: float
    stereo_fps: float
    notes: str


@dataclass(frozen=True)
class S3dRoiChainRow:
    camera: str
    frames: int
    positives: int
    s3d_tp: int
    s3d_fp: int
    s3d_fn: int
    roi_contains: int
    roi_yolo_tp: int
    roi_yolo_fp: int
    roi_yolo_fn: int
    final_tp: int
    final_fp: int
    final_fn: int
    s3d_recall: float
    roi_contains_rate: float
    roi_yolo_conditional_recall: float
    final_recall: float
    final_precision: float
    s3d_median_ms: float
    roi_yolo_median_ms: float
    total_median_ms: float
    stereo_fps: float


def parse_tile_profile(value: str) -> TileProfile:
    parts = value.split(":")
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("tile profile must be name:width:height:overlap")
    name, width_text, height_text, overlap_text = parts
    if not name:
        raise argparse.ArgumentTypeError("tile profile name must not be empty")
    try:
        width = int(width_text)
        height = int(height_text)
        overlap = int(overlap_text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("tile profile width, height, and overlap must be integers") from exc
    if width <= 0 or height <= 0:
        raise argparse.ArgumentTypeError("tile profile width and height must be positive")
    if overlap < 0:
        raise argparse.ArgumentTypeError("tile profile overlap must be non-negative")
    return TileProfile(name=name, tile_width=width, tile_height=height, overlap=overlap)


def parse_imgsz_values(value: str) -> list[int]:
    try:
        sizes = [int(item.strip()) for item in value.split(",") if item.strip()]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("imgsz values must be comma-separated integers") from exc
    if not sizes:
        raise argparse.ArgumentTypeError("provide at least one imgsz value")
    if any(size <= 0 for size in sizes):
        raise argparse.ArgumentTypeError("imgsz values must be positive")
    return sizes


def parse_roi_profile(value: str) -> RoiProfile:
    parts = value.split(":")
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("ROI profile must be name:width:height:imgsz")
    name, width_text, height_text, imgsz_text = parts
    if not name:
        raise argparse.ArgumentTypeError("ROI profile name must not be empty")
    try:
        width = int(width_text)
        height = int(height_text)
        imgsz = int(imgsz_text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("ROI profile width, height, and imgsz must be integers") from exc
    if width <= 0 or height <= 0 or imgsz <= 0:
        raise argparse.ArgumentTypeError("ROI profile width, height, and imgsz must be positive")
    return RoiProfile(name=name, crop_width=width, crop_height=height, imgsz=imgsz)


def axis_starts(length: int, tile: int, overlap: int) -> list[int]:
    if tile >= length:
        return [0]
    stride = max(1, tile - overlap)
    starts = list(range(0, length - tile + 1, stride))
    if starts[-1] != length - tile:
        starts.append(length - tile)
    return sorted(set(starts))


def make_cases(tile_profiles: list[TileProfile], imgsz_values: list[int]) -> list[BenchmarkCase]:
    return [BenchmarkCase(profile=profile, imgsz=imgsz) for profile in tile_profiles for imgsz in imgsz_values]


def dry_run_row(case: BenchmarkCase, frame_width: int, frame_height: int) -> DryRunRow:
    x_tiles = len(axis_starts(frame_width, min(frame_width, case.profile.tile_width), case.profile.overlap))
    y_tiles = len(axis_starts(frame_height, min(frame_height, case.profile.tile_height), case.profile.overlap))
    tiles_per_camera = x_tiles * y_tiles
    sources_per_stereo = 2 * tiles_per_camera
    model_input_mpix = sources_per_stereo * case.imgsz * case.imgsz / 1_000_000.0
    crop_mpix = (
        sources_per_stereo
        * min(frame_width, case.profile.tile_width)
        * min(frame_height, case.profile.tile_height)
        / 1_000_000.0
    )
    return DryRunRow(
        case=case,
        x_tiles=x_tiles,
        y_tiles=y_tiles,
        tiles_per_camera=tiles_per_camera,
        sources_per_stereo=sources_per_stereo,
        model_input_mpix=model_input_mpix,
        crop_mpix=crop_mpix,
    )


def percentile_95(values: list[float]) -> float:
    if len(values) == 1:
        return values[0]
    return statistics.quantiles(values, n=20, method="inclusive")[18]


def safe_median(values: list[float]) -> float:
    return statistics.median(values) if values else 0.0


def label_path_for_image(image_path: Path) -> Path:
    parts = list(image_path.parts)
    for index, part in enumerate(parts):
        if part == "images":
            parts[index] = "labels"
            return Path(*parts).with_suffix(".txt")
    return image_path.with_suffix(".txt")


def load_sample_paths(sample_list: Path, sample_limit: int, real_only: bool) -> list[Path]:
    paths = [Path(line.strip()) for line in sample_list.read_text(encoding="utf-8").splitlines() if line.strip()]
    if real_only:
        paths = [path for path in paths if "/runs/" not in path.as_posix()]
    if sample_limit > 0:
        paths = paths[:sample_limit]
    return paths


def frame_sort_key(path: Path) -> tuple[str, int, str]:
    match = FRAME_NUMBER_RE.search(path.stem)
    frame = int(match.group("frame")) if match else -1
    prefix = path.stem[: match.start()] if match else path.stem
    return prefix, frame, str(path)


def load_sequence_paths(sequence_glob: str, sample_limit: int) -> list[Path]:
    paths = sorted((Path(item) for item in glob(sequence_glob)), key=frame_sort_key)
    if sample_limit > 0:
        paths = paths[:sample_limit]
    return paths


def load_gt_boxes(label_path: Path, width: int, height: int) -> tuple[DetBox, ...]:
    if not label_path.is_file():
        return ()
    boxes: list[DetBox] = []
    for line in label_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        _, xc_text, yc_text, bw_text, bh_text = parts[:5]
        xc = float(xc_text) * width
        yc = float(yc_text) * height
        bw = float(bw_text) * width
        bh = float(bh_text) * height
        boxes.append(DetBox(x1=xc - bw / 2.0, y1=yc - bh / 2.0, x2=xc + bw / 2.0, y2=yc + bh / 2.0))
    return tuple(boxes)


def iou_box(a: DetBox, b: DetBox) -> float:
    ix1 = max(a.x1, b.x1)
    iy1 = max(a.y1, b.y1)
    ix2 = min(a.x2, b.x2)
    iy2 = min(a.y2, b.y2)
    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    intersection = iw * ih
    if intersection <= 0.0:
        return 0.0
    area_a = max(0.0, a.x2 - a.x1) * max(0.0, a.y2 - a.y1)
    area_b = max(0.0, b.x2 - b.x1) * max(0.0, b.y2 - b.y1)
    union = area_a + area_b - intersection
    return intersection / union if union > 0.0 else 0.0


def match_counts(gt_by_image: list[tuple[DetBox, ...]], pred_by_image: list[list[DetBox]], match_iou: float) -> tuple[int, int, int]:
    tp = fp = fn = 0
    for gt_boxes, pred_boxes in zip(gt_by_image, pred_by_image, strict=True):
        matched: set[int] = set()
        for pred in sorted(pred_boxes, key=lambda box: box.conf, reverse=True):
            best_index = -1
            best_iou = 0.0
            for index, gt in enumerate(gt_boxes):
                if index in matched:
                    continue
                candidate_iou = iou_box(pred, gt)
                if candidate_iou > best_iou:
                    best_index = index
                    best_iou = candidate_iou
            if best_index >= 0 and best_iou >= match_iou:
                matched.add(best_index)
                tp += 1
            else:
                fp += 1
        fn += len(gt_boxes) - len(matched)
    return tp, fp, fn


def crop_bounds(cx: float, cy: float, crop_width: int, crop_height: int, image_width: int, image_height: int) -> tuple[int, int, int, int]:
    crop_width = min(crop_width, image_width)
    crop_height = min(crop_height, image_height)
    x1 = int(round(cx - crop_width / 2.0))
    y1 = int(round(cy - crop_height / 2.0))
    x1 = min(max(0, x1), image_width - crop_width)
    y1 = min(max(0, y1), image_height - crop_height)
    return x1, y1, x1 + crop_width, y1 + crop_height


def box_center(box: DetBox) -> tuple[float, float]:
    return (box.x1 + box.x2) / 2.0, (box.y1 + box.y2) / 2.0


def point_hits_any_box(x: float, y: float, boxes: tuple[DetBox, ...], radius_px: float) -> bool:
    for box in boxes:
        cx, cy = box_center(box)
        if ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 <= radius_px:
            return True
    return False


def crop_contains_any_box(crop: tuple[int, int, int, int], boxes: tuple[DetBox, ...]) -> bool:
    x1, y1, x2, y2 = crop
    for box in boxes:
        cx, cy = box_center(box)
        if x1 <= cx <= x2 and y1 <= cy <= y2:
            return True
    return False


def synchronize(torch_module: Any) -> None:
    if torch_module.cuda.is_available():
        torch_module.cuda.synchronize()


def benchmark_case(
    *,
    model: Any,
    np_module: Any,
    torch_module: Any,
    dry: DryRunRow,
    frame_width: int,
    frame_height: int,
    repeats: int,
    warmup: int,
    device: str | None,
    conf: float,
    iou: float,
    max_detections: int,
    seed: int,
) -> TimedRow:
    tile_width = min(frame_width, dry.case.profile.tile_width)
    tile_height = min(frame_height, dry.case.profile.tile_height)
    rng = np_module.random.default_rng(seed)
    per_camera_tiles = [
        rng.integers(0, 256, size=(tile_height, tile_width, 3), dtype=np_module.uint8)
        for _ in range(dry.tiles_per_camera)
    ]
    full_frame_mode = (
        dry.tiles_per_camera == 1
        and dry.case.profile.tile_width >= frame_width
        and dry.case.profile.tile_height >= frame_height
    )
    if full_frame_mode:
        stereo_sources = [
            rng.integers(0, 256, size=(frame_height, frame_width, 3), dtype=np_module.uint8)
            for _ in range(2)
        ]
    else:
        stereo_sources = per_camera_tiles

    def predict_current_stereo() -> None:
        if full_frame_mode:
            model.predict(
                source=stereo_sources,
                imgsz=dry.case.imgsz,
                conf=conf,
                iou=iou,
                max_det=max_detections,
                device=device,
                stream=False,
                verbose=False,
            )
            return
        model.predict(
            source=per_camera_tiles,
            imgsz=dry.case.imgsz,
            conf=conf,
            iou=iou,
            max_det=max_detections,
            device=device,
            stream=False,
            verbose=False,
        )
        model.predict(
            source=per_camera_tiles,
            imgsz=dry.case.imgsz,
            conf=conf,
            iou=iou,
            max_det=max_detections,
            device=device,
            stream=False,
            verbose=False,
        )

    if torch_module.cuda.is_available():
        torch_module.cuda.empty_cache()
        torch_module.cuda.reset_peak_memory_stats()

    try:
        for _ in range(warmup):
            predict_current_stereo()
        synchronize(torch_module)

        elapsed_ms: list[float] = []
        for _ in range(repeats):
            start = time.perf_counter()
            predict_current_stereo()
            synchronize(torch_module)
            elapsed_ms.append((time.perf_counter() - start) * 1000.0)

        peak_cuda_mb = None
        if torch_module.cuda.is_available():
            peak_cuda_mb = torch_module.cuda.max_memory_allocated() / (1024.0 * 1024.0)
        median_ms = statistics.median(elapsed_ms)
        return TimedRow(
            dry=dry,
            mean_ms=statistics.mean(elapsed_ms),
            median_ms=median_ms,
            p95_ms=percentile_95(elapsed_ms),
            min_ms=min(elapsed_ms),
            max_ms=max(elapsed_ms),
            fps=1000.0 / median_ms if median_ms > 0 else 0.0,
            peak_cuda_mb=peak_cuda_mb,
        )
    except RuntimeError as exc:
        if torch_module.cuda.is_available():
            torch_module.cuda.empty_cache()
        return TimedRow(
            dry=dry,
            mean_ms=0.0,
            median_ms=0.0,
            p95_ms=0.0,
            min_ms=0.0,
            max_ms=0.0,
            fps=0.0,
            peak_cuda_mb=None,
            error=str(exc).splitlines()[0],
        )


def format_table(rows: list[DryRunRow | TimedRow], *, timed: bool) -> str:
    if timed:
        header = (
            "| profile | tile | overlap | imgsz | tiles/cam | sources/stereo | "
            "model MPix | crop MPix | median ms | p95 ms | FPS | CUDA MB | status |"
        )
        sep = "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"
        lines = [header, sep]
        for row in rows:
            assert isinstance(row, TimedRow)
            dry = row.dry
            status = "ok" if row.error is None else row.error.replace("|", "/")
            cuda_mb = "" if row.peak_cuda_mb is None else f"{row.peak_cuda_mb:.0f}"
            lines.append(
                "| "
                f"{dry.case.profile.name} | "
                f"{dry.case.profile.tile_width}x{dry.case.profile.tile_height} | "
                f"{dry.case.profile.overlap} | "
                f"{dry.case.imgsz} | "
                f"{dry.tiles_per_camera} ({dry.x_tiles}x{dry.y_tiles}) | "
                f"{dry.sources_per_stereo} | "
                f"{dry.model_input_mpix:.2f} | "
                f"{dry.crop_mpix:.2f} | "
                f"{row.median_ms:.1f} | "
                f"{row.p95_ms:.1f} | "
                f"{row.fps:.2f} | "
                f"{cuda_mb} | "
                f"{status} |"
            )
        return "\n".join(lines)

    header = "| profile | tile | overlap | imgsz | tiles/cam | sources/stereo | model MPix | crop MPix |"
    sep = "|---|---:|---:|---:|---:|---:|---:|---:|"
    lines = [header, sep]
    for row in rows:
        assert isinstance(row, DryRunRow)
        lines.append(
            "| "
            f"{row.case.profile.name} | "
            f"{row.case.profile.tile_width}x{row.case.profile.tile_height} | "
            f"{row.case.profile.overlap} | "
            f"{row.case.imgsz} | "
            f"{row.tiles_per_camera} ({row.x_tiles}x{row.y_tiles}) | "
            f"{row.sources_per_stereo} | "
            f"{row.model_input_mpix:.2f} | "
            f"{row.crop_mpix:.2f} |"
        )
    return "\n".join(lines)


def build_report(
    *,
    rows: list[TimedRow],
    model_path: Path,
    frame_width: int,
    frame_height: int,
    repeats: int,
    warmup: int,
    device: str | None,
    torch_module: Any,
) -> str:
    device_name = "cpu"
    cuda_available = bool(torch_module.cuda.is_available())
    device_value = "" if device is None else str(device).strip()
    if cuda_available and device_value.lower() != "cpu":
        first_device = "0" if device_value in {"", "0"} else device_value.split(",")[0]
        if first_device.startswith("cuda:"):
            first_device = first_device.removeprefix("cuda:")
        device_name = torch_module.cuda.get_device_name(int(first_device))
    lines = [
        f"# YOLO Tile Random Input Benchmark Result - {datetime.now().strftime('%Y-%m-%d')}",
        "",
        "## Scope",
        "",
        "This benchmark uses the current YOLO model with random uint8 image inputs.",
        "It does not use camera capture, real images, stereo matching, or trajectory code.",
        "The timing is intended to compare tile size and `imgsz` cost for first-pass recognition experiments.",
        "",
        "## Settings",
        "",
        f"- Model: `{model_path}`",
        f"- Frame: `{frame_width}x{frame_height}`",
        f"- Warmup iterations: `{warmup}`",
        f"- Timed iterations: `{repeats}`",
        f"- Device argument: `{device if device is not None else ''}`",
        f"- CUDA available: `{cuda_available}`",
        f"- Device name: `{device_name}`",
        f"- Torch: `{torch_module.__version__}`",
        "",
        "## Results",
        "",
        format_table(rows, timed=True),
        "",
        "## Notes",
        "",
        "- `tiles/cam` is computed with the same current tiling math as the runtime tools.",
        "- `sources/stereo` is the number of image inputs processed for one left+right stereo frame.",
        "- `model MPix` is `sources/stereo * imgsz * imgsz`, a useful proxy for GPU model cost.",
        "- `crop MPix` is the total tile image area fed to preprocessing for one stereo frame.",
        "- `FPS` is `1000 / median_ms` for one stereo frame under this benchmark.",
    ]
    return "\n".join(lines) + "\n"


def format_roi_table(rows: list[RoiSampleRow]) -> str:
    header = (
        "| mode | profile | imgsz | images | gt | TP | FP | FN | recall | precision | "
        "median ms/img | p95 ms/img | est stereo FPS | notes |"
    )
    sep = "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"
    lines = [header, sep]
    for row in rows:
        lines.append(
            "| "
            f"{row.mode} | "
            f"{row.profile} | "
            f"{row.imgsz} | "
            f"{row.images} | "
            f"{row.gt} | "
            f"{row.tp} | "
            f"{row.fp} | "
            f"{row.fn} | "
            f"{row.recall:.3f} | "
            f"{row.precision:.3f} | "
            f"{row.median_ms:.2f} | "
            f"{row.p95_ms:.2f} | "
            f"{row.stereo_fps:.2f} | "
            f"{row.notes.replace('|', '/')} |"
        )
    return "\n".join(lines)


def predict_det_boxes(
    *,
    model: Any,
    image: Any,
    imgsz: int,
    conf: float,
    iou: float,
    max_detections: int,
    device: str | None,
    offset_x: int = 0,
    offset_y: int = 0,
) -> list[DetBox]:
    result = model.predict(
        source=image,
        imgsz=imgsz,
        conf=conf,
        iou=iou,
        max_det=max_detections,
        device=device,
        stream=False,
        verbose=False,
    )[0]
    if result.boxes is None or not len(result.boxes):
        return []
    xyxy = result.boxes.xyxy.cpu().numpy().tolist()
    confs = result.boxes.conf.cpu().numpy().tolist()
    return [
        DetBox(
            x1=float(box[0]) + offset_x,
            y1=float(box[1]) + offset_y,
            x2=float(box[2]) + offset_x,
            y2=float(box[3]) + offset_y,
            conf=float(score),
        )
        for box, score in zip(xyxy, confs, strict=True)
    ]


def make_roi_row(
    *,
    mode: str,
    profile: str,
    imgsz: str,
    samples: list[RoiSample],
    pred_by_image: list[list[DetBox]],
    elapsed_ms: list[float],
    match_iou: float,
    notes: str,
) -> RoiSampleRow:
    gt_by_image = [sample.gt_boxes for sample in samples]
    tp, fp, fn = match_counts(gt_by_image, pred_by_image, match_iou)
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    median_ms = statistics.median(elapsed_ms)
    p95_ms = percentile_95(elapsed_ms)
    return RoiSampleRow(
        mode=mode,
        profile=profile,
        imgsz=imgsz,
        images=len(samples),
        gt=sum(len(sample.gt_boxes) for sample in samples),
        tp=tp,
        fp=fp,
        fn=fn,
        recall=recall,
        precision=precision,
        median_ms=median_ms,
        p95_ms=p95_ms,
        stereo_fps=1000.0 / (2.0 * median_ms) if median_ms > 0.0 else 0.0,
        notes=notes,
    )


def build_roi_report(
    *,
    rows: list[RoiSampleRow],
    model_path: Path,
    sample_list: Path,
    sample_limit: int,
    real_only: bool,
    coarse_imgsz: int,
    conf: float,
    iou: float,
    match_iou: float,
    device: str | None,
    torch_module: Any,
) -> str:
    lines = [
        f"# YOLO Runtime ROI Proof Result - {datetime.now().strftime('%Y-%m-%d')}",
        "",
        "## Scope",
        "",
        "This is an offline detector-throughput proof for the existing model.",
        "It does not use ROS/Gazebo, camera capture, stereo triangulation, target prediction, or chassis control.",
        "The `oracle_roi` rows use labels to place the crop and are only an upper bound for locked ROI runtime.",
        "The `coarse_roi` rows prove the full-frame-to-ROI crop path runs, but they are not a real tracker validation.",
        "",
        "## Proof Plan",
        "",
        "1. Measure the current full-frame detector at several `imgsz` values.",
        "2. Measure one-crop locked ROI inference with label-placed crops to estimate the best possible detector budget after ROI lock.",
        "3. Measure same-frame full coarse detection plus ROI refinement to prove the crop chain runs and expose its real cost.",
        "4. Decide whether training should wait for a stateful runtime proof.",
        "",
        "## Settings",
        "",
        f"- Model: `{model_path}`",
        f"- Sample list: `{sample_list}`",
        f"- Sample limit: `{sample_limit}`",
        f"- Real images only: `{real_only}`",
        f"- Coarse full-frame imgsz: `{coarse_imgsz}`",
        f"- Confidence threshold: `{conf}`",
        f"- Prediction IoU setting: `{iou}`",
        f"- Match IoU: `{match_iou}`",
        f"- Device argument: `{device if device is not None else ''}`",
        f"- CUDA available: `{bool(torch_module.cuda.is_available())}`",
        f"- Torch: `{torch_module.__version__}`",
        "",
        "## Results",
        "",
        format_roi_table(rows),
        "",
        "## Readout",
        "",
        "- `full` is the current full-frame detector path on one camera frame.",
        "- `oracle_roi` measures one crop per camera frame after the ROI is already known.",
        "- `coarse_roi` runs a full-frame coarse pass, crops around the best coarse detection, then runs ROI refinement.",
        "- `est stereo FPS` assumes left and right camera images are processed sequentially with the same per-image median.",
        "- Passing `30 FPS` in `oracle_roi` only proves detector budget feasibility while locked; it does not prove tracking or real catch-loop behavior.",
        "",
        "## Small Object Compression Note",
        "",
        "- Training cannot recover image detail that was destroyed by full-frame downscaling.",
        "- A `10px` to `16px` tennis ball in a `3840px`-wide frame becomes roughly `0.8px` to `1.7px` at `imgsz=320/416`.",
        "- The same object inside a `960px`-wide ROI becomes roughly `3.3px` to `6.9px` at `imgsz=320/416`.",
        "- This is why ROI/crop must happen before the YOLO resize step; otherwise the far-ball signal is already gone.",
        "",
        "## Decision",
        "",
        "- Low-`imgsz` full-frame rows can meet the FPS target, but their recall is too low for the tennis-ball task.",
        "- Low-`imgsz` locked ROI rows can meet the FPS target in this detector-only proof and have much better recall than full-frame at the same `imgsz`.",
        "- Same-frame `coarse_roi` does not meet the FPS target because it runs two detections per camera frame.",
        "- The next runtime step is a stateful ROI mode: full-frame search only while unlocked or periodically, then ROI-only inference while locked.",
        "- This is not a target-board or ROS/Gazebo proof; do not start more training until that stateful runtime mode is implemented and measured.",
    ]
    return "\n".join(lines) + "\n"


def cmd_benchmark_roi_sample(args: argparse.Namespace) -> int:
    if args.sample_limit < 0:
        print("error: --sample-limit must be non-negative")
        return 2
    if args.max_detections <= 0:
        print("error: --max-detections must be positive")
        return 2
    if args.coarse_imgsz <= 0:
        print("error: --coarse-imgsz must be positive")
        return 2
    if not args.sample_list.is_file():
        print(f"error: sample list not found: {args.sample_list}")
        return 2

    roi_profile_values = list(DEFAULT_ROI_PROFILES) if args.roi_profile is None else args.roi_profile
    roi_profiles = [parse_roi_profile(item) for item in roi_profile_values]
    full_imgsz_values = parse_imgsz_values(args.full_imgsz_values)
    sample_paths = load_sample_paths(args.sample_list, args.sample_limit, args.real_only)

    if args.dry_run:
        print(f"samples={len(sample_paths)}")
        print("full_imgsz=" + ",".join(str(value) for value in full_imgsz_values))
        print("roi_profiles=" + ",".join(profile.name for profile in roi_profiles))
        return 0

    if not args.model.is_file():
        print(f"error: model not found: {args.model}")
        return 2
    if not sample_paths:
        print("error: no sample images selected")
        return 2

    try:
        import cv2
        import torch
        from ultralytics import YOLO
    except ImportError as exc:
        print(
            "error: ROI benchmark requires opencv-python, torch, and ultralytics. "
            "Run with `uv run --extra detect tennisbot-yolo benchmark roi-sample ...`."
        )
        print(f"missing: {exc}")
        return 2

    if args.threads > 0:
        torch.set_num_threads(args.threads)
        try:
            torch.set_num_interop_threads(1)
        except RuntimeError:
            pass

    samples: list[RoiSample] = []
    images: list[Any] = []
    for image_path in sample_paths:
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            print(f"error: failed to read image: {image_path}")
            return 2
        height, width = image.shape[:2]
        samples.append(
            RoiSample(
                image=image_path,
                width=width,
                height=height,
                gt_boxes=load_gt_boxes(label_path_for_image(image_path), width, height),
            )
        )
        images.append(image)

    model = YOLO(str(args.model))
    rows: list[RoiSampleRow] = []

    # Keep model setup outside timing.
    predict_det_boxes(
        model=model,
        image=images[0],
        imgsz=full_imgsz_values[0],
        conf=args.conf,
        iou=args.iou,
        max_detections=args.max_detections,
        device=args.device,
    )

    for imgsz in full_imgsz_values:
        pred_by_image: list[list[DetBox]] = []
        elapsed_ms: list[float] = []
        for image in images:
            start = time.perf_counter()
            pred_by_image.append(
                predict_det_boxes(
                    model=model,
                    image=image,
                    imgsz=imgsz,
                    conf=args.conf,
                    iou=args.iou,
                    max_detections=args.max_detections,
                    device=args.device,
                )
            )
            elapsed_ms.append((time.perf_counter() - start) * 1000.0)
        rows.append(
            make_roi_row(
                mode="full",
                profile=f"full_{imgsz}",
                imgsz=str(imgsz),
                samples=samples,
                pred_by_image=pred_by_image,
                elapsed_ms=elapsed_ms,
                match_iou=args.match_iou,
                notes="full-frame baseline",
            )
        )

    for profile in roi_profiles:
        pred_by_image = []
        elapsed_ms = []
        for sample, image in zip(samples, images, strict=True):
            if sample.gt_boxes:
                anchor = max(sample.gt_boxes, key=lambda box: (box.x2 - box.x1) * (box.y2 - box.y1))
                cx = (anchor.x1 + anchor.x2) / 2.0
                cy = (anchor.y1 + anchor.y2) / 2.0
            else:
                cx = sample.width / 2.0
                cy = sample.height / 2.0
            x1, y1, x2, y2 = crop_bounds(cx, cy, profile.crop_width, profile.crop_height, sample.width, sample.height)
            crop = image[y1:y2, x1:x2]
            start = time.perf_counter()
            pred_by_image.append(
                predict_det_boxes(
                    model=model,
                    image=crop,
                    imgsz=profile.imgsz,
                    conf=args.conf,
                    iou=args.iou,
                    max_detections=args.max_detections,
                    device=args.device,
                    offset_x=x1,
                    offset_y=y1,
                )
            )
            elapsed_ms.append((time.perf_counter() - start) * 1000.0)
        rows.append(
            make_roi_row(
                mode="oracle_roi",
                profile=f"{profile.name} ({profile.crop_width}x{profile.crop_height})",
                imgsz=str(profile.imgsz),
                samples=samples,
                pred_by_image=pred_by_image,
                elapsed_ms=elapsed_ms,
                match_iou=args.match_iou,
                notes="label-placed ROI upper bound",
            )
        )

    for profile in roi_profiles:
        pred_by_image = []
        elapsed_ms = []
        for sample, image in zip(samples, images, strict=True):
            start = time.perf_counter()
            coarse_boxes = predict_det_boxes(
                model=model,
                image=image,
                imgsz=args.coarse_imgsz,
                conf=args.conf,
                iou=args.iou,
                max_detections=args.max_detections,
                device=args.device,
            )
            if coarse_boxes:
                anchor = max(coarse_boxes, key=lambda box: box.conf)
                cx = (anchor.x1 + anchor.x2) / 2.0
                cy = (anchor.y1 + anchor.y2) / 2.0
            else:
                cx = sample.width / 2.0
                cy = sample.height / 2.0
            x1, y1, x2, y2 = crop_bounds(cx, cy, profile.crop_width, profile.crop_height, sample.width, sample.height)
            crop = image[y1:y2, x1:x2]
            pred_by_image.append(
                predict_det_boxes(
                    model=model,
                    image=crop,
                    imgsz=profile.imgsz,
                    conf=args.conf,
                    iou=args.iou,
                    max_detections=args.max_detections,
                    device=args.device,
                    offset_x=x1,
                    offset_y=y1,
                )
            )
            elapsed_ms.append((time.perf_counter() - start) * 1000.0)
        rows.append(
            make_roi_row(
                mode="coarse_roi",
                profile=f"{profile.name} ({profile.crop_width}x{profile.crop_height})",
                imgsz=f"{args.coarse_imgsz}+{profile.imgsz}",
                samples=samples,
                pred_by_image=pred_by_image,
                elapsed_ms=elapsed_ms,
                match_iou=args.match_iou,
                notes="same-frame full coarse plus ROI",
            )
        )

    report = build_roi_report(
        rows=rows,
        model_path=args.model,
        sample_list=args.sample_list,
        sample_limit=args.sample_limit,
        real_only=args.real_only,
        coarse_imgsz=args.coarse_imgsz,
        conf=args.conf,
        iou=args.iou,
        match_iou=args.match_iou,
        device=args.device,
        torch_module=torch,
    )
    print(report)
    if args.output_markdown is not None:
        args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
        args.output_markdown.write_text(report, encoding="utf-8")
        print(f"wrote={args.output_markdown}")
    return 0


def build_roi_track_report(
    *,
    row: RoiSampleRow,
    search_model_path: Path,
    roi_model_path: Path,
    sequence_glob: str,
    config: RoiTrackConfig,
    mode_counts: dict[str, int],
    conf: float,
    iou: float,
    match_iou: float,
    device: str | None,
    torch_module: Any,
    same_frame_search_on_miss_imgsz: int,
) -> str:
    lines = [
        f"# YOLO Stateful ROI Replay Result - {datetime.now().strftime('%Y-%m-%d')}",
        "",
        "## Scope",
        "",
        "This replay exercises a stateful visual ROI tracker on an ordered real-frame sequence.",
        "It decides whether each frame runs full-frame search or ROI-only inference.",
        "It does not use ROS/Gazebo, stereo triangulation, target prediction, or chassis control.",
        "",
        "## Settings",
        "",
        f"- Search model: `{search_model_path}`",
        f"- ROI model: `{roi_model_path}`",
        f"- Sequence glob: `{sequence_glob}`",
        f"- Search imgsz: `{config.search_imgsz}`",
        f"- ROI: `{config.roi_width}x{config.roi_height}` at imgsz `{config.roi_imgsz}`",
        f"- Expanded ROI: `{config.expanded_width}x{config.expanded_height}`",
        f"- Lost after misses: `{config.lost_after_misses}`",
        f"- Expand after misses: `{config.expand_after_misses}`",
        f"- Edge margin ratio: `{config.edge_margin_ratio}`",
        f"- Distance score weight: `{config.distance_score_weight}`",
        f"- Max update distance ratio: `{config.max_update_distance_ratio}`",
        f"- Candidate confirmation frames: `{config.candidate_confirmation_frames}`",
        f"- Acquire confirmation frames: `{config.acquire_confirmation_frames}`",
        f"- Candidate match distance ratio: `{config.candidate_match_distance_ratio}`",
        f"- Same-frame search-on-miss imgsz: `{same_frame_search_on_miss_imgsz}`",
        f"- Confidence threshold: `{conf}`",
        f"- Prediction IoU setting: `{iou}`",
        f"- Match IoU: `{match_iou}`",
        f"- Device argument: `{device if device is not None else ''}`",
        f"- CUDA available: `{bool(torch_module.cuda.is_available())}`",
        f"- Torch: `{torch_module.__version__}`",
        "",
        "## Mode Counts",
        "",
        f"- Search frames: `{mode_counts.get('search', 0)}`",
        f"- ROI frames: `{mode_counts.get('roi', 0)}`",
        f"- Expanded ROI frames: `{mode_counts.get('expanded', 0)}`",
        f"- Same-frame search-on-miss frames: `{mode_counts.get('same_frame_search', 0)}`",
        f"- Lock acquisitions: `{mode_counts.get('acquired', 0)}`",
        f"- Lost events: `{mode_counts.get('lost', 0)}`",
        f"- Detection updates used by tracker: `{mode_counts.get('updates', 0)}`",
        "",
        "## Result",
        "",
        format_roi_table([row]),
        "",
        "## Readout",
        "",
        "- This is closer to the intended runtime than `coarse_roi`, because locked frames do not also run full-frame search.",
        "- The result still uses one monocular image sequence and estimates stereo FPS as sequential left+right processing.",
        "- If the tracker locks onto false positives, precision and recall will expose that in this replay.",
        "- Full ROS/Gazebo catch-loop validation is still separate and must use the real backend pose/control chain.",
    ]
    return "\n".join(lines) + "\n"


def cmd_benchmark_roi_track(args: argparse.Namespace) -> int:
    if args.sample_limit < 0:
        print("error: --sample-limit must be non-negative")
        return 2
    if args.max_detections <= 0:
        print("error: --max-detections must be positive")
        return 2
    if args.threads < 0:
        print("error: --threads must be nonnegative")
        return 2

    sequence_glob = str(args.sequence_glob)
    sample_paths = load_sequence_paths(sequence_glob, args.sample_limit)
    if args.dry_run:
        print(f"samples={len(sample_paths)}")
        if sample_paths:
            print(f"first={sample_paths[0]}")
            print(f"last={sample_paths[-1]}")
        return 0

    search_model_path = args.model
    roi_model_path = args.roi_model if args.roi_model is not None else args.model
    if not search_model_path.is_file():
        print(f"error: model not found: {search_model_path}")
        return 2
    if not roi_model_path.is_file():
        print(f"error: ROI model not found: {roi_model_path}")
        return 2
    if not sample_paths:
        print(f"error: no images matched sequence glob: {sequence_glob}")
        return 2

    try:
        import cv2
        import torch
        from ultralytics import YOLO
    except ImportError as exc:
        print(
            "error: ROI track benchmark requires opencv-python, torch, and ultralytics. "
            "Run with `uv run --extra detect tennisbot-yolo benchmark roi-track ...`."
        )
        print(f"missing: {exc}")
        return 2

    if args.threads > 0:
        torch.set_num_threads(args.threads)
        try:
            torch.set_num_interop_threads(1)
        except RuntimeError:
            pass

    samples: list[RoiSample] = []
    images: list[Any] = []
    for image_path in sample_paths:
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            print(f"error: failed to read image: {image_path}")
            return 2
        height, width = image.shape[:2]
        samples.append(
            RoiSample(
                image=image_path,
                width=width,
                height=height,
                gt_boxes=load_gt_boxes(label_path_for_image(image_path), width, height),
            )
        )
        images.append(image)

    config = RoiTrackConfig(
        roi_width=args.roi_width,
        roi_height=args.roi_height,
        expanded_width=args.expanded_width,
        expanded_height=args.expanded_height,
        search_imgsz=args.search_imgsz,
        roi_imgsz=args.roi_imgsz,
        lost_after_misses=args.lost_after_misses,
        expand_after_misses=args.expand_after_misses,
        edge_margin_ratio=args.edge_margin_ratio,
        velocity_alpha=args.velocity_alpha,
        min_lock_confidence=args.min_lock_confidence,
        distance_score_weight=args.distance_score_weight,
        max_update_distance_ratio=args.max_update_distance_ratio,
        candidate_confirmation_frames=args.candidate_confirmation_frames,
        acquire_confirmation_frames=args.acquire_confirmation_frames,
        candidate_match_distance_ratio=args.candidate_match_distance_ratio,
    )
    tracker = StatefulRoiTracker(config)
    search_model = YOLO(str(search_model_path))
    if roi_model_path.resolve() == search_model_path.resolve():
        roi_model = search_model
    else:
        roi_model = YOLO(str(roi_model_path))
    predict_det_boxes(
        model=search_model,
        image=images[0],
        imgsz=config.search_imgsz,
        conf=args.conf,
        iou=args.iou,
        max_detections=args.max_detections,
        device=args.device,
    )
    predict_det_boxes(
        model=roi_model,
        image=images[0],
        imgsz=config.roi_imgsz,
        conf=args.conf,
        iou=args.iou,
        max_detections=args.max_detections,
        device=args.device,
    )

    pred_by_image: list[list[DetBox]] = []
    elapsed_ms: list[float] = []
    mode_counts = {
        "search": 0,
        "roi": 0,
        "expanded": 0,
        "same_frame_search": 0,
        "acquired": 0,
        "lost": 0,
        "updates": 0,
    }
    for sample, image in zip(samples, images, strict=True):
        window = tracker.window(sample.width, sample.height)
        mode_counts[window.mode] += 1
        if window.expanded:
            mode_counts["expanded"] += 1
        if window.mode == "search":
            active_model = search_model
            source = image
            offset_x = 0
            offset_y = 0
        else:
            active_model = roi_model
            source = image[window.y1 : window.y2, window.x1 : window.x2]
            offset_x = window.x1
            offset_y = window.y1

        start = time.perf_counter()
        detections = predict_det_boxes(
            model=active_model,
            image=source,
            imgsz=window.imgsz,
            conf=args.conf,
            iou=args.iou,
            max_detections=args.max_detections,
            device=args.device,
            offset_x=offset_x,
            offset_y=offset_y,
        )
        update = tracker.update(detections, frame_width=sample.width, frame_height=sample.height, window=window)

        def record_update_counts(current_update: Any) -> None:
            if current_update.acquired:
                mode_counts["acquired"] += 1
            if current_update.lost:
                mode_counts["lost"] += 1
            if current_update.detection_used:
                mode_counts["updates"] += 1

        record_update_counts(update)

        if (
            args.same_frame_search_on_miss_imgsz > 0
            and window.mode == "roi"
            and not update.detection_used
        ):
            mode_counts["same_frame_search"] += 1
            recovery_window = CropWindow(
                mode="search",
                x1=0,
                y1=0,
                x2=sample.width,
                y2=sample.height,
                imgsz=args.same_frame_search_on_miss_imgsz,
            )
            detections = predict_det_boxes(
                model=search_model,
                image=image,
                imgsz=args.same_frame_search_on_miss_imgsz,
                conf=args.conf,
                iou=args.iou,
                max_detections=args.max_detections,
                device=args.device,
            )
            recovery_update = tracker.update(
                detections,
                frame_width=sample.width,
                frame_height=sample.height,
                window=recovery_window,
            )
            record_update_counts(recovery_update)

        elapsed_ms.append((time.perf_counter() - start) * 1000.0)
        pred_by_image.append(detections)

    notes = (
        f"search={mode_counts['search']} roi={mode_counts['roi']} expanded={mode_counts['expanded']} "
        f"acquired={mode_counts['acquired']} lost={mode_counts['lost']}"
    )
    row = make_roi_row(
        mode="stateful_roi",
        profile=f"{config.roi_width}x{config.roi_height}->{config.expanded_width}x{config.expanded_height}",
        imgsz=f"{config.search_imgsz}/{config.roi_imgsz}",
        samples=samples,
        pred_by_image=pred_by_image,
        elapsed_ms=elapsed_ms,
        match_iou=args.match_iou,
        notes=notes,
    )
    report = build_roi_track_report(
        row=row,
        search_model_path=search_model_path,
        roi_model_path=roi_model_path,
        sequence_glob=sequence_glob,
        config=config,
        mode_counts=mode_counts,
        conf=args.conf,
        iou=args.iou,
        match_iou=args.match_iou,
        device=args.device,
        torch_module=torch,
        same_frame_search_on_miss_imgsz=args.same_frame_search_on_miss_imgsz,
    )
    print(report)
    if args.output_markdown is not None:
        args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
        args.output_markdown.write_text(report, encoding="utf-8")
        print(f"wrote={args.output_markdown}")
    return 0


def camera_name_for_path(path: Path) -> str:
    match = re.search(r"_(cam\d+)_frame_", path.stem)
    return match.group(1) if match else "unknown"


def load_s3d_checkpoint(checkpoint_path: Path, *, device: str) -> tuple[Any, int, int, int, str]:
    import torch

    from .temporal_heatmap import build_model, input_channels_for_mode

    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    window = int(checkpoint.get("window", 0))
    input_width = int(checkpoint.get("input_width", 0))
    input_height = int(checkpoint.get("input_height", 0))
    input_mode = str(checkpoint.get("input_mode", "rgb"))
    if window <= 0 or window % 2 != 1:
        raise ValueError("S3d checkpoint does not define a valid odd window")
    if input_width <= 0 or input_height <= 0:
        raise ValueError("S3d checkpoint does not define valid input dimensions")
    model = build_model(input_channels=input_channels_for_mode(window, input_mode))
    model.load_state_dict(checkpoint["model_state"])
    model.to(device)
    model.eval()
    return model, window, input_width, input_height, input_mode


def predict_s3d_peak(
    *,
    model: Any,
    window_images: list[Any],
    input_width: int,
    input_height: int,
    input_mode: str,
    device: str,
) -> tuple[float, float, float]:
    import cv2
    import torch

    from .temporal_heatmap import compose_temporal_input

    tensors = []
    for image in window_images:
        resized = cv2.resize(image, (input_width, input_height), interpolation=cv2.INTER_AREA)
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        tensor = torch.from_numpy(rgb).permute(2, 0, 1).float().div_(255.0)
        tensors.append(tensor)
    model_input = compose_temporal_input(tensors, input_mode).unsqueeze(0).to(device)
    with torch.no_grad():
        heatmap = torch.sigmoid(model(model_input))[0, 0]
        flat_index = int(torch.argmax(heatmap).item())
        score = float(heatmap.flatten()[flat_index].item())
        y = flat_index // int(heatmap.shape[1])
        x = flat_index % int(heatmap.shape[1])
    return float(x), float(y), score


def format_s3d_roi_chain_table(rows: list[S3dRoiChainRow]) -> str:
    header = (
        "| camera | frames | positives | S3d TP/FP/FN | S3d recall | ROI contains | "
        "ROI YOLO cond recall | final TP/FP/FN | final recall | final precision | "
        "S3d ms | ROI YOLO ms | total ms | est stereo FPS |"
    )
    sep = "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"
    lines = [header, sep]
    for row in rows:
        lines.append(
            "| "
            f"{row.camera} | "
            f"{row.frames} | "
            f"{row.positives} | "
            f"{row.s3d_tp}/{row.s3d_fp}/{row.s3d_fn} | "
            f"{row.s3d_recall:.3f} | "
            f"{row.roi_contains}/{row.s3d_tp} ({row.roi_contains_rate:.3f}) | "
            f"{row.roi_yolo_conditional_recall:.3f} | "
            f"{row.final_tp}/{row.final_fp}/{row.final_fn} | "
            f"{row.final_recall:.3f} | "
            f"{row.final_precision:.3f} | "
            f"{row.s3d_median_ms:.2f} | "
            f"{row.roi_yolo_median_ms:.2f} | "
            f"{row.total_median_ms:.2f} | "
            f"{row.stereo_fps:.2f} |"
        )
    return "\n".join(lines)


def build_s3d_roi_chain_report(
    *,
    rows: list[S3dRoiChainRow],
    checkpoint_path: Path,
    roi_model_path: Path,
    sequence_glob: str,
    roi_width: int,
    roi_height: int,
    roi_imgsz: int,
    threshold: float,
    radius_px: float,
    conf: float,
    iou: float,
    match_iou: float,
    s3d_device: str,
    yolo_device: str | None,
    torch_module: Any,
) -> str:
    lines = [
        f"# S3d Search + ROI YOLO Chain Result - {datetime.now().strftime('%Y-%m-%d')}",
        "",
        "## Scope",
        "",
        "This is an offline monocular replay of `S3d full-frame temporal heatmap search -> ROI crop -> ROI YOLO refinement`.",
        "It does not use ROS/Gazebo, camera capture, stereo triangulation, target prediction, or chassis control.",
        "It answers whether the current S3d search output can feed the existing ROI YOLO detector without losing most recall.",
        "",
        "## Settings",
        "",
        f"- S3d checkpoint: `{checkpoint_path}`",
        f"- ROI YOLO model: `{roi_model_path}`",
        f"- Sequence glob: `{sequence_glob}`",
        f"- ROI crop: `{roi_width}x{roi_height}`",
        f"- ROI YOLO imgsz: `{roi_imgsz}`",
        f"- S3d threshold: `{threshold}`",
        f"- S3d hit radius: `{radius_px}` px at S3d input scale",
        f"- YOLO confidence: `{conf}`",
        f"- YOLO prediction IoU: `{iou}`",
        f"- YOLO match IoU: `{match_iou}`",
        f"- S3d device: `{s3d_device}`",
        f"- YOLO device: `{yolo_device if yolo_device is not None else ''}`",
        f"- CUDA available: `{bool(torch_module.cuda.is_available())}`",
        f"- Torch: `{torch_module.__version__}`",
        "",
        "## Results",
        "",
        format_s3d_roi_chain_table(rows),
        "",
        "## Metric Definitions",
        "",
        "- `S3d recall` counts a positive frame as found only when the heatmap peak is above threshold and within the radius of the labeled ball center.",
        "- `ROI contains` counts S3d true positives whose crop contains the labeled ball center before YOLO refinement.",
        "- `ROI YOLO cond recall` is ROI YOLO recall only on frames where S3d was a true positive and the ROI contained the ball center.",
        "- `final recall` is the full chain recall against all labeled positives in that camera sequence.",
        "- `est stereo FPS` assumes the same per-camera median cost is paid sequentially for left and right images.",
        "",
        "## Readout",
        "",
        "- If `ROI YOLO cond recall` is high but `final recall` is limited, the bottleneck is S3d search/localization.",
        "- If `ROI YOLO cond recall` is low, the ROI detector or crop size needs work before runtime integration.",
        "- This experiment still does not prove real stereo runtime; it only validates the detector chain on saved frames.",
    ]
    return "\n".join(lines) + "\n"


def cmd_benchmark_s3d_roi_chain(args: argparse.Namespace) -> int:
    if args.sample_limit < 0:
        print("error: --sample-limit must be non-negative")
        return 2
    if args.roi_width <= 0 or args.roi_height <= 0 or args.roi_imgsz <= 0:
        print("error: ROI dimensions and imgsz must be positive")
        return 2
    if args.max_detections <= 0:
        print("error: --max-detections must be positive")
        return 2
    if not args.checkpoint.is_file():
        print(f"error: S3d checkpoint not found: {args.checkpoint}")
        return 2
    if not args.roi_model.is_file():
        print(f"error: ROI YOLO model not found: {args.roi_model}")
        return 2

    sample_paths = load_sequence_paths(str(args.sequence_glob), args.sample_limit)
    if args.dry_run:
        print(f"samples={len(sample_paths)}")
        if sample_paths:
            print(f"first={sample_paths[0]}")
            print(f"last={sample_paths[-1]}")
            cameras = sorted({camera_name_for_path(path) for path in sample_paths})
            print("cameras=" + ",".join(cameras))
        return 0
    if not sample_paths:
        print(f"error: no images matched sequence glob: {args.sequence_glob}")
        return 2

    try:
        import cv2
        import torch
        from ultralytics import YOLO
    except ImportError as exc:
        print(
            "error: S3d ROI chain benchmark requires opencv-python, torch, and ultralytics. "
            "Run with `uv run --extra detect tennisbot-yolo benchmark s3d-roi-chain ...`."
        )
        print(f"missing: {exc}")
        return 2

    if args.threads > 0:
        torch.set_num_threads(args.threads)
        try:
            torch.set_num_interop_threads(1)
        except RuntimeError:
            pass

    s3d_device = args.s3d_device
    if s3d_device == "auto":
        s3d_device = "cuda:0" if torch.cuda.is_available() else "cpu"
    s3d_model, window, input_width, input_height, input_mode = load_s3d_checkpoint(
        args.checkpoint,
        device=s3d_device,
    )
    radius = window // 2
    by_camera: dict[str, list[Path]] = {}
    for path in sample_paths:
        by_camera.setdefault(camera_name_for_path(path), []).append(path)

    roi_model = YOLO(str(args.roi_model))
    rows: list[S3dRoiChainRow] = []
    for camera, paths in sorted(by_camera.items()):
        images: list[Any] = []
        samples: list[RoiSample] = []
        for image_path in sorted(paths, key=frame_sort_key):
            image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
            if image is None:
                print(f"error: failed to read image: {image_path}")
                return 2
            height, width = image.shape[:2]
            images.append(image)
            samples.append(
                RoiSample(
                    image=image_path,
                    width=width,
                    height=height,
                    gt_boxes=load_gt_boxes(label_path_for_image(image_path), width, height),
                )
            )
        if len(samples) <= radius * 2:
            continue

        predict_det_boxes(
            model=roi_model,
            image=images[radius],
            imgsz=args.roi_imgsz,
            conf=args.conf,
            iou=args.iou,
            max_detections=args.max_detections,
            device=args.yolo_device,
        )

        positives = 0
        s3d_tp = s3d_fp = s3d_fn = 0
        roi_contains = 0
        roi_cond_samples: list[RoiSample] = []
        roi_cond_predictions: list[list[DetBox]] = []
        final_gt_by_image: list[tuple[DetBox, ...]] = []
        final_pred_by_image: list[list[DetBox]] = []
        s3d_elapsed_ms: list[float] = []
        roi_elapsed_ms: list[float] = []
        total_elapsed_ms: list[float] = []

        for index in range(radius, len(samples) - radius):
            sample = samples[index]
            gt_boxes = sample.gt_boxes
            if gt_boxes:
                positives += len(gt_boxes)

            s3d_start = time.perf_counter()
            peak_x, peak_y, score = predict_s3d_peak(
                model=s3d_model,
                window_images=images[index - radius : index + radius + 1],
                input_width=input_width,
                input_height=input_height,
                input_mode=input_mode,
                device=s3d_device,
            )
            synchronize(torch)
            s3d_ms = (time.perf_counter() - s3d_start) * 1000.0
            s3d_elapsed_ms.append(s3d_ms)

            scale_x = sample.width / input_width
            scale_y = sample.height / input_height
            full_x = peak_x * scale_x
            full_y = peak_y * scale_y
            detected = score >= args.threshold
            localized = bool(gt_boxes) and point_hits_any_box(
                peak_x,
                peak_y,
                tuple(
                    DetBox(
                        x1=box.x1 / scale_x,
                        y1=box.y1 / scale_y,
                        x2=box.x2 / scale_x,
                        y2=box.y2 / scale_y,
                    )
                    for box in gt_boxes
                ),
                args.radius_px,
            )

            if detected and localized:
                s3d_tp += 1
            elif detected:
                s3d_fp += 1
                if gt_boxes:
                    s3d_fn += len(gt_boxes)
            elif gt_boxes:
                s3d_fn += len(gt_boxes)

            frame_roi_elapsed = 0.0
            frame_predictions: list[DetBox] = []
            if detected:
                crop = crop_bounds(full_x, full_y, args.roi_width, args.roi_height, sample.width, sample.height)
                contains = crop_contains_any_box(crop, gt_boxes)
                if localized and contains:
                    roi_contains += 1
                x1, y1, x2, y2 = crop
                crop_image = images[index][y1:y2, x1:x2]
                roi_start = time.perf_counter()
                frame_predictions = predict_det_boxes(
                    model=roi_model,
                    image=crop_image,
                    imgsz=args.roi_imgsz,
                    conf=args.conf,
                    iou=args.iou,
                    max_detections=args.max_detections,
                    device=args.yolo_device,
                    offset_x=x1,
                    offset_y=y1,
                )
                synchronize(torch)
                frame_roi_elapsed = (time.perf_counter() - roi_start) * 1000.0
                roi_elapsed_ms.append(frame_roi_elapsed)
                if localized and contains:
                    roi_cond_samples.append(sample)
                    roi_cond_predictions.append(frame_predictions)

            final_gt_by_image.append(gt_boxes)
            final_pred_by_image.append(frame_predictions)
            total_elapsed_ms.append(s3d_ms + frame_roi_elapsed)

        roi_yolo_tp, roi_yolo_fp, roi_yolo_fn = match_counts(
            [sample.gt_boxes for sample in roi_cond_samples],
            roi_cond_predictions,
            args.match_iou,
        )
        final_tp, final_fp, final_fn = match_counts(final_gt_by_image, final_pred_by_image, args.match_iou)
        s3d_recall = s3d_tp / positives if positives else 0.0
        roi_contains_rate = roi_contains / s3d_tp if s3d_tp else 0.0
        roi_yolo_conditional_recall = (
            roi_yolo_tp / (roi_yolo_tp + roi_yolo_fn) if (roi_yolo_tp + roi_yolo_fn) else 0.0
        )
        final_recall = final_tp / (final_tp + final_fn) if (final_tp + final_fn) else 0.0
        final_precision = final_tp / (final_tp + final_fp) if (final_tp + final_fp) else 0.0
        total_median_ms = safe_median(total_elapsed_ms)
        rows.append(
            S3dRoiChainRow(
                camera=camera,
                frames=len(total_elapsed_ms),
                positives=positives,
                s3d_tp=s3d_tp,
                s3d_fp=s3d_fp,
                s3d_fn=s3d_fn,
                roi_contains=roi_contains,
                roi_yolo_tp=roi_yolo_tp,
                roi_yolo_fp=roi_yolo_fp,
                roi_yolo_fn=roi_yolo_fn,
                final_tp=final_tp,
                final_fp=final_fp,
                final_fn=final_fn,
                s3d_recall=s3d_recall,
                roi_contains_rate=roi_contains_rate,
                roi_yolo_conditional_recall=roi_yolo_conditional_recall,
                final_recall=final_recall,
                final_precision=final_precision,
                s3d_median_ms=safe_median(s3d_elapsed_ms),
                roi_yolo_median_ms=safe_median(roi_elapsed_ms),
                total_median_ms=total_median_ms,
                stereo_fps=1000.0 / (2.0 * total_median_ms) if total_median_ms > 0.0 else 0.0,
            )
        )

    report = build_s3d_roi_chain_report(
        rows=rows,
        checkpoint_path=args.checkpoint,
        roi_model_path=args.roi_model,
        sequence_glob=str(args.sequence_glob),
        roi_width=args.roi_width,
        roi_height=args.roi_height,
        roi_imgsz=args.roi_imgsz,
        threshold=args.threshold,
        radius_px=args.radius_px,
        conf=args.conf,
        iou=args.iou,
        match_iou=args.match_iou,
        s3d_device=s3d_device,
        yolo_device=args.yolo_device,
        torch_module=torch,
    )
    print(report)
    if args.output_markdown is not None:
        args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
        args.output_markdown.write_text(report, encoding="utf-8")
        print(f"wrote={args.output_markdown}")
    return 0


def cmd_benchmark_tiles(args: argparse.Namespace) -> int:
    if args.frame_width <= 0 or args.frame_height <= 0:
        print("error: frame dimensions must be positive")
        return 2
    if args.repeats <= 0:
        print("error: --repeats must be positive")
        return 2
    if args.warmup < 0:
        print("error: --warmup must be non-negative")
        return 2
    if args.max_detections <= 0:
        print("error: --max-detections must be positive")
        return 2

    tile_profile_values = list(DEFAULT_TILE_PROFILES) if args.tile_profile is None else args.tile_profile
    tile_profiles = [parse_tile_profile(item) for item in tile_profile_values]
    imgsz_values = parse_imgsz_values(args.imgsz_values)
    cases = make_cases(tile_profiles, imgsz_values)
    dry_rows = [dry_run_row(case, args.frame_width, args.frame_height) for case in cases]

    if args.dry_run:
        print(format_table(dry_rows, timed=False))
        return 0

    if not args.model.is_file():
        print(f"error: model not found: {args.model}")
        return 2

    try:
        import numpy as np
        import torch
        from ultralytics import YOLO
    except ImportError as exc:
        print(
            "error: benchmark requires numpy, torch, and ultralytics. "
            "Run with `uv run --extra detect tennisbot-yolo benchmark tiles ...`."
        )
        print(f"missing: {exc}")
        return 2

    model = YOLO(str(args.model))
    rows = [
        benchmark_case(
            model=model,
            np_module=np,
            torch_module=torch,
            dry=dry,
            frame_width=args.frame_width,
            frame_height=args.frame_height,
            repeats=args.repeats,
            warmup=args.warmup,
            device=args.device,
            conf=args.conf,
            iou=args.iou,
            max_detections=args.max_detections,
            seed=args.seed + index,
        )
        for index, dry in enumerate(dry_rows)
    ]
    report = build_report(
        rows=rows,
        model_path=args.model,
        frame_width=args.frame_width,
        frame_height=args.frame_height,
        repeats=args.repeats,
        warmup=args.warmup,
        device=args.device,
        torch_module=torch,
    )
    print(report)
    if args.output_markdown is not None:
        args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
        args.output_markdown.write_text(report, encoding="utf-8")
        print(f"wrote={args.output_markdown}")
    return 0


def add_benchmark_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser_kwargs = {"formatter_class": argparse.ArgumentDefaultsHelpFormatter}
    benchmark = subparsers.add_parser("benchmark", help="运行 YOLO 随机输入性能基准。", **parser_kwargs)
    benchmark_subparsers = benchmark.add_subparsers(dest="benchmark_command", required=True)

    tiles = benchmark_subparsers.add_parser("tiles", help="对比 4K tile profile 和 imgsz 的推理成本。", **parser_kwargs)
    tiles.add_argument("--model", type=Path, default=DEFAULT_MODEL, help="Ultralytics YOLO .pt 模型路径")
    tiles.add_argument("--frame-width", type=int, default=3840, help="原始相机帧宽度")
    tiles.add_argument("--frame-height", type=int, default=2160, help="原始相机帧高度")
    tiles.add_argument(
        "--tile-profile",
        action="append",
        default=None,
        help="tile profile，格式 name:width:height:overlap；可重复",
    )
    tiles.add_argument("--imgsz-values", default=DEFAULT_IMGSZ_VALUES, help="逗号分隔的 YOLO imgsz 值")
    tiles.add_argument("--repeats", type=int, default=8, help="计时迭代次数")
    tiles.add_argument("--warmup", type=int, default=2, help="预热迭代次数")
    tiles.add_argument("--device", default="0", help="Ultralytics device，例如 cpu、0 或 0,1")
    tiles.add_argument("--conf", type=float, default=0.05, help="置信度阈值")
    tiles.add_argument("--iou", type=float, default=0.5, help="NMS IoU 阈值")
    tiles.add_argument("--max-detections", type=int, default=6, help="每图最大检测数")
    tiles.add_argument("--seed", type=int, default=20260704, help="随机输入种子")
    tiles.add_argument("--output-markdown", type=Path, help="写入 Markdown 结果文件")
    tiles.add_argument("--dry-run", action="store_true", help="只打印 profile 和 tile 计数，不加载模型")
    tiles.set_defaults(func=cmd_benchmark_tiles)

    roi = benchmark_subparsers.add_parser(
        "roi-sample",
        help="用真实样本验证 full-frame/ROI 检测吞吐和召回。",
        **parser_kwargs,
    )
    roi.add_argument("--model", type=Path, default=DEFAULT_MODEL, help="Ultralytics YOLO .pt 模型路径")
    roi.add_argument("--sample-list", type=Path, default=DEFAULT_ROI_SAMPLE_LIST, help="样本图片列表")
    roi.add_argument("--sample-limit", type=int, default=60, help="最多读取多少张样本；0 表示全量")
    roi.add_argument("--real-only", action="store_true", help="跳过 copy-paste augmentation 生成图，只使用真实源图")
    roi.add_argument("--full-imgsz-values", default="416,512,640", help="全图 baseline 的 YOLO imgsz 列表")
    roi.add_argument(
        "--roi-profile",
        action="append",
        default=None,
        help="ROI profile，格式 name:width:height:imgsz；可重复",
    )
    roi.add_argument("--coarse-imgsz", type=int, default=416, help="coarse+ROI 模式的全图粗检测 imgsz")
    roi.add_argument("--device", default="cpu", help="Ultralytics device，例如 cpu、0 或 0,1")
    roi.add_argument("--threads", type=int, default=10, help="CPU torch 线程数；0 表示不修改")
    roi.add_argument("--conf", type=float, default=0.05, help="置信度阈值")
    roi.add_argument("--iou", type=float, default=0.7, help="预测阶段 IoU 阈值")
    roi.add_argument("--match-iou", type=float, default=0.5, help="评估匹配 IoU 阈值")
    roi.add_argument("--max-detections", type=int, default=300, help="每图最大检测数")
    roi.add_argument("--output-markdown", type=Path, help="写入 Markdown 结果文件")
    roi.add_argument("--dry-run", action="store_true", help="只打印样本和 profile，不加载模型")
    roi.set_defaults(func=cmd_benchmark_roi_sample)

    track = benchmark_subparsers.add_parser(
        "roi-track",
        help="按有序真实帧 replay stateful ROI 搜索/锁定逻辑。",
        **parser_kwargs,
    )
    track.add_argument("--model", type=Path, default=DEFAULT_MODEL, help="Ultralytics YOLO .pt 模型路径")
    track.add_argument("--roi-model", type=Path, default=None, help="LOCKED ROI 阶段使用的 YOLO .pt；默认复用 --model")
    track.add_argument("--sequence-glob", default=str(DEFAULT_ROI_TRACK_GLOB), help="有序帧 glob")
    track.add_argument("--sample-limit", type=int, default=0, help="最多读取多少张样本；0 表示全量")
    track.add_argument("--search-imgsz", type=int, default=320, help="SEARCH 全图检测 imgsz")
    track.add_argument("--roi-imgsz", type=int, default=320, help="LOCKED ROI 检测 imgsz")
    track.add_argument("--roi-width", type=int, default=960, help="LOCKED 正常 ROI 宽度")
    track.add_argument("--roi-height", type=int, default=540, help="LOCKED 正常 ROI 高度")
    track.add_argument("--expanded-width", type=int, default=1280, help="miss/靠边后的扩展 ROI 宽度")
    track.add_argument("--expanded-height", type=int, default=720, help="miss/靠边后的扩展 ROI 高度")
    track.add_argument("--lost-after-misses", type=int, default=3, help="连续 miss 多少帧后回到 SEARCH")
    track.add_argument("--expand-after-misses", type=int, default=1, help="连续 miss 多少帧后先扩窗")
    track.add_argument("--edge-margin-ratio", type=float, default=0.20, help="检测靠 ROI 边缘多少比例内则下一帧扩窗")
    track.add_argument("--velocity-alpha", type=float, default=0.60, help="像素速度 EMA 权重")
    track.add_argument("--min-lock-confidence", type=float, default=0.05, help="用于锁定/更新 ROI 的最低置信度")
    track.add_argument("--distance-score-weight", type=float, default=0.35, help="LOCKED 时检测离预测中心越远的打分惩罚")
    track.add_argument("--max-update-distance-ratio", type=float, default=0.50, help="超过窗口对角线该比例的大跳变需确认")
    track.add_argument("--candidate-confirmation-frames", type=int, default=2, help="LOCKED 大跳变候选需要连续确认的帧数")
    track.add_argument("--acquire-confirmation-frames", type=int, default=1, help="SEARCH 获取锁定需要连续确认的帧数")
    track.add_argument("--candidate-match-distance-ratio", type=float, default=0.20, help="候选连续确认时允许的中心距离比例")
    track.add_argument("--same-frame-search-on-miss-imgsz", type=int, default=0, help="LOCKED ROI 未被接受时同帧追加全图 search；0 表示关闭")
    track.add_argument("--device", default="cpu", help="Ultralytics device，例如 cpu、0 或 0,1")
    track.add_argument("--threads", type=int, default=10, help="CPU torch 线程数；0 表示不修改")
    track.add_argument("--conf", type=float, default=0.05, help="置信度阈值")
    track.add_argument("--iou", type=float, default=0.7, help="预测阶段 IoU 阈值")
    track.add_argument("--match-iou", type=float, default=0.5, help="评估匹配 IoU 阈值")
    track.add_argument("--max-detections", type=int, default=300, help="每图最大检测数")
    track.add_argument("--output-markdown", type=Path, help="写入 Markdown 结果文件")
    track.add_argument("--dry-run", action="store_true", help="只打印匹配的序列帧，不加载模型")
    track.set_defaults(func=cmd_benchmark_roi_track)

    s3d_roi = benchmark_subparsers.add_parser(
        "s3d-roi-chain",
        help="离线 replay S3d heatmap search 后接 ROI YOLO 的检测链路。",
        **parser_kwargs,
    )
    s3d_roi.add_argument("--checkpoint", type=Path, default=DEFAULT_S3D_CHECKPOINT, help="S3d temporal heatmap checkpoint")
    s3d_roi.add_argument("--roi-model", type=Path, default=DEFAULT_MODEL, help="ROI 阶段 YOLO .pt 模型")
    s3d_roi.add_argument("--sequence-glob", default=str(DEFAULT_S3D_ROI_GLOB), help="有序帧 glob，可同时包含 cam1/cam2")
    s3d_roi.add_argument("--sample-limit", type=int, default=0, help="最多读取多少张样本；0 表示全量")
    s3d_roi.add_argument("--roi-width", type=int, default=960, help="S3d 球心周围 ROI 宽度")
    s3d_roi.add_argument("--roi-height", type=int, default=540, help="S3d 球心周围 ROI 高度")
    s3d_roi.add_argument("--roi-imgsz", type=int, default=320, help="ROI YOLO imgsz")
    s3d_roi.add_argument("--threshold", type=float, default=0.40, help="S3d heatmap peak score 阈值")
    s3d_roi.add_argument("--radius-px", type=float, default=12.0, help="S3d input 尺度下命中半径")
    s3d_roi.add_argument("--s3d-device", default="auto", help="S3d torch device；auto/cpu/cuda:0")
    s3d_roi.add_argument("--yolo-device", default=None, help="Ultralytics device，例如 cpu、0 或 0,1")
    s3d_roi.add_argument("--threads", type=int, default=10, help="CPU torch 线程数；0 表示不修改")
    s3d_roi.add_argument("--conf", type=float, default=0.05, help="ROI YOLO 置信度阈值")
    s3d_roi.add_argument("--iou", type=float, default=0.7, help="ROI YOLO 预测阶段 IoU 阈值")
    s3d_roi.add_argument("--match-iou", type=float, default=0.5, help="ROI YOLO bbox 评估匹配 IoU 阈值")
    s3d_roi.add_argument("--max-detections", type=int, default=300, help="每图最大检测数")
    s3d_roi.add_argument("--output-markdown", type=Path, help="写入 Markdown 结果文件")
    s3d_roi.add_argument("--dry-run", action="store_true", help="只打印匹配的序列帧，不加载模型")
    s3d_roi.set_defaults(func=cmd_benchmark_s3d_roi_chain)

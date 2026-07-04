from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import statistics
import time
from typing import Any

from .paths import REPO_ROOT


DEFAULT_MODEL = REPO_ROOT / "artifacts" / "models" / "tennis_ball_yolo" / "model.pt"
DEFAULT_TILE_PROFILES = (
    "full_4k:3840:2160:0",
    "tile_2048x1216:2048:1216:160",
    "tile_2048x1152:2048:1152:160",
    "tile_1536x864:1536:864:160",
)
DEFAULT_IMGSZ_VALUES = "960,1280,1536"


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

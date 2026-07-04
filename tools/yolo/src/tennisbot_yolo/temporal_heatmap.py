from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import random
import re
import statistics
import time
from typing import Any

from .dataset import IMAGE_SUFFIXES, read_yolo_labels
from .paths import DEFAULT_IMAGES_ROOT, DEFAULT_LABELS_ROOT, DEFAULT_RUNS_ROOT, DEFAULT_SPRITES_ROOT


FRAME_RE = re.compile(r"(?P<prefix>.+)_frame_(?P<frame>\d+)$")
DEFAULT_VAL_TOKEN = "20260701_155008"
DEFAULT_RUN_NAME = "search_s3_temporal_heatmap_20260704"


@dataclass(frozen=True)
class FrameRef:
    image_path: Path
    label_path: Path
    sequence_key: str
    frame_index: int


@dataclass(frozen=True)
class HeatmapSample:
    window_paths: tuple[Path, ...]
    center_image: Path
    label_path: Path
    sequence_key: str
    frame_index: int
    positive: bool
    x_center: float = 0.0
    y_center: float = 0.0
    box_width: float = 0.0
    box_height: float = 0.0


@dataclass(frozen=True)
class PeakPrediction:
    score: float
    x: float
    y: float
    positive: bool
    gt_x: float
    gt_y: float


@dataclass(frozen=True)
class PeakMetrics:
    threshold: float
    tp: int
    fp: int
    fn: int
    positives: int
    negatives: int
    recall: float
    precision: float
    f1: float
    mean_tp_distance: float | None
    oracle_recall: float


@dataclass(frozen=True)
class SyntheticConfig:
    backgrounds: tuple[Path, ...]
    sprites: tuple[Path, ...]
    count: int
    window: int
    input_width: int
    input_height: int
    sigma: float
    seed: int
    sprite_scale_min: float
    sprite_scale_max: float
    motion_px_min: float
    motion_px_max: float
    blur_probability: float


def frame_sort_key(path: Path) -> tuple[str, int, str]:
    match = FRAME_RE.match(path.stem)
    if not match:
        return path.stem, -1, str(path)
    return match.group("prefix"), int(match.group("frame")), str(path)


def parse_token_list(value: str | None) -> tuple[str, ...]:
    if value is None:
        return ()
    return tuple(token.strip() for token in value.split(",") if token.strip())


def label_path_for_image(image_path: Path, images_root: Path, labels_root: Path) -> Path:
    return labels_root / image_path.relative_to(images_root).with_suffix(".txt")


def best_label(labels: list[Any]) -> Any | None:
    if not labels:
        return None
    return max(labels, key=lambda label: label.width * label.height)


def collect_frame_refs(
    *,
    images_root: Path,
    labels_root: Path,
    include_tokens: tuple[str, ...] = (),
    exclude_tokens: tuple[str, ...] = (),
) -> dict[str, dict[int, FrameRef]]:
    frames: dict[str, dict[int, FrameRef]] = {}
    for image_path in sorted(
        (
            path
            for path in images_root.rglob("*")
            if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
        ),
        key=frame_sort_key,
    ):
        match = FRAME_RE.match(image_path.stem)
        if not match:
            continue
        rel_parent = image_path.parent.relative_to(images_root).as_posix()
        sequence_key = f"{rel_parent}/{match.group('prefix')}"
        haystack = f"{sequence_key}/{image_path.name}"
        if include_tokens and not any(token in haystack for token in include_tokens):
            continue
        if exclude_tokens and any(token in haystack for token in exclude_tokens):
            continue
        label_path = label_path_for_image(image_path, images_root, labels_root)
        frames.setdefault(sequence_key, {})[int(match.group("frame"))] = FrameRef(
            image_path=image_path,
            label_path=label_path,
            sequence_key=sequence_key,
            frame_index=int(match.group("frame")),
        )
    return frames


def build_temporal_samples(
    *,
    images_root: Path,
    labels_root: Path,
    window: int,
    include_tokens: tuple[str, ...] = (),
    exclude_tokens: tuple[str, ...] = (),
    include_empty_labels: bool = True,
) -> list[HeatmapSample]:
    if window <= 0 or window % 2 != 1:
        raise ValueError("window must be a positive odd integer")
    radius = window // 2
    samples: list[HeatmapSample] = []
    frame_groups = collect_frame_refs(
        images_root=images_root,
        labels_root=labels_root,
        include_tokens=include_tokens,
        exclude_tokens=exclude_tokens,
    )
    for sequence_key, frames in sorted(frame_groups.items()):
        for frame_index, center in sorted(frames.items()):
            if not center.label_path.is_file():
                continue
            labels = read_yolo_labels(center.label_path)
            label = best_label(labels)
            if label is None and not include_empty_labels:
                continue
            window_refs: list[Path] = []
            missing = False
            for offset in range(-radius, radius + 1):
                ref = frames.get(frame_index + offset)
                if ref is None:
                    missing = True
                    break
                window_refs.append(ref.image_path)
            if missing:
                continue
            if label is None:
                samples.append(
                    HeatmapSample(
                        window_paths=tuple(window_refs),
                        center_image=center.image_path,
                        label_path=center.label_path,
                        sequence_key=sequence_key,
                        frame_index=frame_index,
                        positive=False,
                    )
                )
                continue
            samples.append(
                HeatmapSample(
                    window_paths=tuple(window_refs),
                    center_image=center.image_path,
                    label_path=center.label_path,
                    sequence_key=sequence_key,
                    frame_index=frame_index,
                    positive=True,
                    x_center=label.x_center,
                    y_center=label.y_center,
                    box_width=label.width,
                    box_height=label.height,
                )
            )
    return samples


def balance_samples(samples: list[HeatmapSample], max_negative_ratio: float, seed: int) -> list[HeatmapSample]:
    if max_negative_ratio < 0:
        raise ValueError("max_negative_ratio must be non-negative")
    positives = [sample for sample in samples if sample.positive]
    negatives = [sample for sample in samples if not sample.positive]
    if not positives or max_negative_ratio == 0:
        return positives
    max_negatives = int(round(len(positives) * max_negative_ratio))
    rng = random.Random(seed)
    rng.shuffle(negatives)
    return sorted(positives + negatives[:max_negatives], key=lambda sample: (sample.sequence_key, sample.frame_index))


def summarize_samples(samples: list[HeatmapSample]) -> tuple[int, int, int]:
    positives = sum(1 for sample in samples if sample.positive)
    negatives = len(samples) - positives
    return len(samples), positives, negatives


def collect_synthetic_backgrounds(
    *,
    images_root: Path,
    labels_root: Path,
    exclude_tokens: tuple[str, ...],
) -> tuple[Path, ...]:
    backgrounds: list[Path] = []
    for image_path in sorted(
        (
            path
            for path in images_root.rglob("*")
            if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
        ),
        key=frame_sort_key,
    ):
        haystack = image_path.relative_to(images_root).as_posix()
        if exclude_tokens and any(token in haystack for token in exclude_tokens):
            continue
        label_path = label_path_for_image(image_path, images_root, labels_root)
        if label_path.is_file() and read_yolo_labels(label_path):
            continue
        backgrounds.append(image_path)
    return tuple(backgrounds)


def collect_synthetic_sprites(sprites_root: Path) -> tuple[Path, ...]:
    if not sprites_root.exists():
        return ()
    sprites = [
        path
        for path in sorted(sprites_root.glob("*.png"))
        if path.is_file() and not path.name.endswith("_crop.png")
    ]
    return tuple(sprites)


def make_heatmap_tensor(
    *,
    torch_module: Any,
    width: int,
    height: int,
    x_center: float,
    y_center: float,
    sigma: float,
) -> Any:
    yy = torch_module.arange(height, dtype=torch_module.float32).view(height, 1)
    xx = torch_module.arange(width, dtype=torch_module.float32).view(1, width)
    cx = x_center * (width - 1)
    cy = y_center * (height - 1)
    heatmap = torch_module.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2.0 * sigma * sigma))
    return heatmap.unsqueeze(0).clamp_(0.0, 1.0)


class TemporalHeatmapDataset:
    def __init__(
        self,
        *,
        samples: list[HeatmapSample],
        input_width: int,
        input_height: int,
        sigma: float,
        augment: bool,
    ) -> None:
        self.samples = samples
        self.input_width = input_width
        self.input_height = input_height
        self.sigma = sigma
        self.augment = augment

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> tuple[Any, Any, Any]:
        import cv2
        import torch

        sample = self.samples[index]
        frames = []
        for image_path in sample.window_paths:
            image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
            if image is None:
                raise FileNotFoundError(f"could not read image: {image_path}")
            resized = cv2.resize(image, (self.input_width, self.input_height), interpolation=cv2.INTER_AREA)
            rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
            tensor = torch.from_numpy(rgb).permute(2, 0, 1).float().div_(255.0)
            frames.append(tensor)
        image_tensor = torch.cat(frames, dim=0)
        if self.augment:
            gain = 0.85 + random.random() * 0.30
            bias = (random.random() - 0.5) * 0.08
            image_tensor = image_tensor.mul(gain).add(bias).clamp_(0.0, 1.0)
        if sample.positive:
            target = make_heatmap_tensor(
                torch_module=torch,
                width=self.input_width,
                height=self.input_height,
                x_center=sample.x_center,
                y_center=sample.y_center,
                sigma=self.sigma,
            )
            meta = torch.tensor([1.0, sample.x_center, sample.y_center], dtype=torch.float32)
        else:
            target = torch.zeros((1, self.input_height, self.input_width), dtype=torch.float32)
            meta = torch.tensor([0.0, 0.0, 0.0], dtype=torch.float32)
        return image_tensor, target, meta


class SyntheticTemporalHeatmapDataset:
    def __init__(self, config: SyntheticConfig) -> None:
        if config.count < 0:
            raise ValueError("synthetic count must be non-negative")
        if not config.backgrounds:
            raise ValueError("synthetic backgrounds must not be empty")
        if not config.sprites:
            raise ValueError("synthetic sprites must not be empty")
        self.config = config

    def __len__(self) -> int:
        return self.config.count

    def __getitem__(self, index: int) -> tuple[Any, Any, Any]:
        import cv2
        import numpy as np
        import torch

        cfg = self.config
        rng = random.Random(cfg.seed + index * 9973)
        background_path = rng.choice(cfg.backgrounds)
        sprite_path = rng.choice(cfg.sprites)

        background = cv2.imread(str(background_path), cv2.IMREAD_COLOR)
        if background is None:
            raise FileNotFoundError(f"could not read synthetic background: {background_path}")
        background = cv2.resize(background, (cfg.input_width, cfg.input_height), interpolation=cv2.INTER_AREA)

        sprite = cv2.imread(str(sprite_path), cv2.IMREAD_UNCHANGED)
        if sprite is None or sprite.ndim != 3 or sprite.shape[2] != 4:
            raise FileNotFoundError(f"could not read synthetic sprite: {sprite_path}")
        scale = rng.uniform(cfg.sprite_scale_min, cfg.sprite_scale_max)
        sprite_width = max(1, int(round(sprite.shape[1] * scale)))
        sprite_height = max(1, int(round(sprite.shape[0] * scale)))
        sprite = cv2.resize(sprite, (sprite_width, sprite_height), interpolation=cv2.INTER_AREA)
        if cfg.blur_probability > 0.0 and rng.random() < cfg.blur_probability:
            kernel = rng.choice([3, 5, 7])
            sprite = cv2.GaussianBlur(sprite, (kernel, kernel), 0)

        max_x = max(0, cfg.input_width - sprite_width - 1)
        max_y = max(0, cfg.input_height - sprite_height - 1)
        center_x = rng.uniform(sprite_width * 0.5, cfg.input_width - sprite_width * 0.5)
        center_y = rng.uniform(sprite_height * 0.5, cfg.input_height - sprite_height * 0.5)
        motion = rng.uniform(cfg.motion_px_min, cfg.motion_px_max)
        angle = rng.uniform(0.0, 2.0 * np.pi)
        dx = np.cos(angle) * motion
        dy = np.sin(angle) * motion
        radius = cfg.window // 2
        frames = []
        center_frame_x = center_x
        center_frame_y = center_y
        alpha_base = sprite[:, :, 3].astype(np.float32) / 255.0
        sprite_rgb = sprite[:, :, :3].astype(np.float32)
        for offset in range(-radius, radius + 1):
            frame = background.copy().astype(np.float32)
            gain = rng.uniform(0.90, 1.10)
            bias = rng.uniform(-12.0, 12.0)
            frame = np.clip(frame * gain + bias, 0.0, 255.0)
            cx = center_x + offset * dx
            cy = center_y + offset * dy
            x = int(round(cx - sprite_width * 0.5))
            y = int(round(cy - sprite_height * 0.5))
            x = max(0, min(max_x, x))
            y = max(0, min(max_y, y))
            if offset == 0:
                center_frame_x = x + sprite_width * 0.5
                center_frame_y = y + sprite_height * 0.5
            region = frame[y : y + sprite_height, x : x + sprite_width]
            alpha = alpha_base[:, :, None]
            frame[y : y + sprite_height, x : x + sprite_width] = sprite_rgb * alpha + region * (1.0 - alpha)
            rgb = cv2.cvtColor(frame.astype(np.uint8), cv2.COLOR_BGR2RGB)
            frames.append(torch.from_numpy(rgb).permute(2, 0, 1).float().div_(255.0))

        image_tensor = torch.cat(frames, dim=0)
        target = make_heatmap_tensor(
            torch_module=torch,
            width=cfg.input_width,
            height=cfg.input_height,
            x_center=center_frame_x / max(1, cfg.input_width - 1),
            y_center=center_frame_y / max(1, cfg.input_height - 1),
            sigma=cfg.sigma,
        )
        meta = torch.tensor(
            [
                1.0,
                center_frame_x / max(1, cfg.input_width - 1),
                center_frame_y / max(1, cfg.input_height - 1),
            ],
            dtype=torch.float32,
        )
        return image_tensor, target, meta


def build_model(input_channels: int) -> Any:
    import torch.nn as nn

    def block(in_channels: int, out_channels: int) -> nn.Sequential:
        groups = 8 if out_channels % 8 == 0 else 1
        return nn.Sequential(
            nn.Conv2d(in_channels, out_channels, 3, padding=1, bias=False),
            nn.GroupNorm(groups, out_channels),
            nn.SiLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, 3, padding=1, bias=False),
            nn.GroupNorm(groups, out_channels),
            nn.SiLU(inplace=True),
        )

    class TinyTemporalHeatmapNet(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.enc1 = block(input_channels, 32)
            self.down1 = nn.Sequential(nn.Conv2d(32, 48, 3, stride=2, padding=1, bias=False), nn.SiLU(inplace=True))
            self.enc2 = block(48, 48)
            self.down2 = nn.Sequential(nn.Conv2d(48, 64, 3, stride=2, padding=1, bias=False), nn.SiLU(inplace=True))
            self.bottleneck = block(64, 64)
            self.up1 = block(64 + 48, 48)
            self.up2 = block(48 + 32, 32)
            self.out = nn.Conv2d(32, 1, 1)

        def forward(self, x: Any) -> Any:
            import torch
            import torch.nn.functional as functional

            e1 = self.enc1(x)
            e2 = self.enc2(self.down1(e1))
            b = self.bottleneck(self.down2(e2))
            u1 = functional.interpolate(b, size=e2.shape[-2:], mode="bilinear", align_corners=False)
            u1 = self.up1(torch.cat([u1, e2], dim=1))
            u2 = functional.interpolate(u1, size=e1.shape[-2:], mode="bilinear", align_corners=False)
            u2 = self.up2(torch.cat([u2, e1], dim=1))
            return self.out(u2)

    return TinyTemporalHeatmapNet()


def compute_peak_metrics(
    predictions: list[PeakPrediction],
    *,
    width: int,
    height: int,
    radius_px: float,
    thresholds: list[float],
) -> PeakMetrics:
    positives = sum(1 for prediction in predictions if prediction.positive)
    negatives = len(predictions) - positives
    oracle_hits = 0
    best: PeakMetrics | None = None
    for threshold in thresholds:
        tp = fp = fn = 0
        tp_distances: list[float] = []
        for prediction in predictions:
            detected = prediction.score >= threshold
            if prediction.positive:
                distance = ((prediction.x - prediction.gt_x) ** 2 + (prediction.y - prediction.gt_y) ** 2) ** 0.5
                localized = distance <= radius_px
                if threshold == thresholds[0] and localized:
                    oracle_hits += 1
                if detected and localized:
                    tp += 1
                    tp_distances.append(distance)
                elif detected:
                    fp += 1
                    fn += 1
                else:
                    fn += 1
            elif detected:
                fp += 1
        recall = tp / positives if positives else 0.0
        precision = tp / (tp + fp) if tp + fp else 0.0
        f1 = 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
        metric = PeakMetrics(
            threshold=threshold,
            tp=tp,
            fp=fp,
            fn=fn,
            positives=positives,
            negatives=negatives,
            recall=recall,
            precision=precision,
            f1=f1,
            mean_tp_distance=statistics.mean(tp_distances) if tp_distances else None,
            oracle_recall=oracle_hits / positives if positives else 0.0,
        )
        if best is None or (metric.f1, metric.recall, metric.precision) > (best.f1, best.recall, best.precision):
            best = metric
    if best is None:
        return PeakMetrics(0.0, 0, 0, 0, positives, negatives, 0.0, 0.0, 0.0, None, 0.0)
    return best


def collect_predictions(model: Any, loader: Any, *, device: str, width: int, height: int) -> list[PeakPrediction]:
    import torch

    predictions: list[PeakPrediction] = []
    model.eval()
    with torch.no_grad():
        for images, _targets, metas in loader:
            images = images.to(device)
            logits = model(images)
            heatmaps = torch.sigmoid(logits).detach().cpu()
            metas = metas.cpu()
            batch, _, heatmap_height, heatmap_width = heatmaps.shape
            flat = heatmaps.view(batch, -1)
            scores, indices = flat.max(dim=1)
            ys = torch.div(indices, heatmap_width, rounding_mode="floor").float()
            xs = (indices % heatmap_width).float()
            for index in range(batch):
                positive = bool(metas[index, 0].item() >= 0.5)
                gt_x = metas[index, 1].item() * (width - 1)
                gt_y = metas[index, 2].item() * (height - 1)
                predictions.append(
                    PeakPrediction(
                        score=float(scores[index].item()),
                        x=float(xs[index].item()),
                        y=float(ys[index].item()),
                        positive=positive,
                        gt_x=float(gt_x),
                        gt_y=float(gt_y),
                    )
                )
    return predictions


def evaluate_model(
    model: Any,
    loader: Any,
    *,
    device: str,
    width: int,
    height: int,
    radius_px: float,
    thresholds: list[float],
) -> PeakMetrics:
    predictions = collect_predictions(model, loader, device=device, width=width, height=height)
    return compute_peak_metrics(predictions, width=width, height=height, radius_px=radius_px, thresholds=thresholds)


def benchmark_latency(model: Any, *, device: str, input_channels: int, height: int, width: int, repeats: int) -> float:
    import torch

    if repeats <= 0:
        return 0.0
    model.eval()
    sample = torch.rand((1, input_channels, height, width), device=device)
    timings: list[float] = []
    with torch.no_grad():
        for _ in range(3):
            _ = model(sample)
        if device.startswith("cuda"):
            torch.cuda.synchronize()
        for _ in range(repeats):
            start = time.perf_counter()
            _ = model(sample)
            if device.startswith("cuda"):
                torch.cuda.synchronize()
            timings.append((time.perf_counter() - start) * 1000.0)
    return statistics.median(timings)


def format_report(
    *,
    args: argparse.Namespace,
    output_dir: Path,
    train_count: tuple[int, int, int],
    real_train_count: tuple[int, int, int],
    synthetic_count: int,
    val_count: tuple[int, int, int],
    best_epoch: int,
    best_loss: float,
    best_metrics: PeakMetrics,
    latency_ms: float,
) -> str:
    distance = "" if best_metrics.mean_tp_distance is None else f"{best_metrics.mean_tp_distance:.2f}"
    stereo_fps = 1000.0 / (latency_ms * 2.0) if latency_ms > 0 else 0.0
    return "\n".join(
        [
            f"# Search-S3 Temporal Heatmap Result - {datetime.now().strftime('%Y-%m-%d')}",
            "",
            "## Scope",
            "",
            "This trains a small temporal heatmap teacher for search/acquisition.",
            "It uses labeled image sequences only and does not validate ROS/Gazebo, stereo triangulation, target prediction, or chassis control.",
            "",
            "## Settings",
            "",
            f"- Output: `{output_dir}`",
            f"- Images root: `{args.images_root}`",
            f"- Labels root: `{args.labels_root}`",
            f"- Window: `{args.window}` frames",
            f"- Input: `{args.input_width}x{args.input_height}`",
            f"- Sigma: `{args.sigma}` px",
            f"- Validation token: `{args.val_include}`",
            f"- Train exclude: `{args.train_exclude}`",
            f"- Device: `{args.device}`",
            f"- Epochs requested: `{args.epochs}`",
            f"- Batch: `{args.batch}`",
            f"- Synthetic train samples: `{synthetic_count}`",
            "",
            "## Data",
            "",
            "| split | samples | positives | negatives |",
            "|---|---:|---:|---:|",
            f"| train | {train_count[0]} | {train_count[1]} | {train_count[2]} |",
            f"| train_real | {real_train_count[0]} | {real_train_count[1]} | {real_train_count[2]} |",
            f"| train_synthetic | {synthetic_count} | {synthetic_count} | 0 |",
            f"| val | {val_count[0]} | {val_count[1]} | {val_count[2]} |",
            "",
            "## Best Validation",
            "",
            "| epoch | loss | threshold | TP | FP | FN | recall | precision | F1 | oracle recall | mean TP dist px |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
            (
                f"| {best_epoch} | {best_loss:.5f} | {best_metrics.threshold:.2f} | "
                f"{best_metrics.tp} | {best_metrics.fp} | {best_metrics.fn} | "
                f"{best_metrics.recall:.3f} | {best_metrics.precision:.3f} | {best_metrics.f1:.3f} | "
                f"{best_metrics.oracle_recall:.3f} | {distance} |"
            ),
            "",
            "## Latency",
            "",
            "| device | input | median ms/frame | estimated stereo FPS |",
            "|---|---|---:|---:|",
            f"| {args.device} | {args.window}xRGB {args.input_width}x{args.input_height} | {latency_ms:.2f} | {stereo_fps:.2f} |",
            "",
            "## Decision",
            "",
            "This is a teacher experiment. It should not be promoted to the CPU runtime unless recall is high and latency is separately validated in the full ROI/search loop.",
        ]
    )


def cmd_temporal_heatmap_train(args: argparse.Namespace) -> int:
    import torch
    import torch.nn.functional as functional
    from torch.utils.data import ConcatDataset, DataLoader

    if args.threads > 0:
        torch.set_num_threads(args.threads)

    seed = int(args.seed)
    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

    device = args.device
    if device == "auto":
        device = "cuda:0" if torch.cuda.is_available() else "cpu"

    images_root = args.images_root.resolve()
    labels_root = args.labels_root.resolve()
    train_exclude = parse_token_list(args.train_exclude)
    val_include = parse_token_list(args.val_include)
    train_include = parse_token_list(args.train_include)

    train_samples = build_temporal_samples(
        images_root=images_root,
        labels_root=labels_root,
        window=args.window,
        include_tokens=train_include,
        exclude_tokens=train_exclude,
        include_empty_labels=True,
    )
    train_samples = balance_samples(train_samples, args.max_negative_ratio, seed)
    val_samples = build_temporal_samples(
        images_root=images_root,
        labels_root=labels_root,
        window=args.window,
        include_tokens=val_include,
        exclude_tokens=(),
        include_empty_labels=True,
    )

    if not train_samples:
        raise SystemExit("no train samples found")
    if not val_samples:
        raise SystemExit("no validation samples found")

    real_train_count = summarize_samples(train_samples)
    train_dataset = TemporalHeatmapDataset(
        samples=train_samples,
        input_width=args.input_width,
        input_height=args.input_height,
        sigma=args.sigma,
        augment=True,
    )
    synthetic_count = int(args.synthetic_count)
    if synthetic_count > 0:
        backgrounds = collect_synthetic_backgrounds(
            images_root=images_root,
            labels_root=labels_root,
            exclude_tokens=train_exclude,
        )
        sprites = collect_synthetic_sprites(args.sprites_root.resolve())
        synthetic_dataset = SyntheticTemporalHeatmapDataset(
            SyntheticConfig(
                backgrounds=backgrounds,
                sprites=sprites,
                count=synthetic_count,
                window=args.window,
                input_width=args.input_width,
                input_height=args.input_height,
                sigma=args.sigma,
                seed=seed + 100_000,
                sprite_scale_min=args.synthetic_sprite_scale_min,
                sprite_scale_max=args.synthetic_sprite_scale_max,
                motion_px_min=args.synthetic_motion_px_min,
                motion_px_max=args.synthetic_motion_px_max,
                blur_probability=args.synthetic_blur_probability,
            )
        )
        train_dataset = ConcatDataset([train_dataset, synthetic_dataset])
    val_dataset = TemporalHeatmapDataset(
        samples=val_samples,
        input_width=args.input_width,
        input_height=args.input_height,
        sigma=args.sigma,
        augment=False,
    )
    train_loader = DataLoader(train_dataset, batch_size=args.batch, shuffle=True, num_workers=args.workers)
    val_loader = DataLoader(val_dataset, batch_size=args.batch, shuffle=False, num_workers=args.workers)

    output_dir = args.output_dir
    if output_dir is None:
        output_dir = DEFAULT_RUNS_ROOT / "temporal_heatmap" / args.name
    output_dir.mkdir(parents=True, exist_ok=True)

    model = build_model(input_channels=args.window * 3).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    thresholds = [float(value) for value in args.thresholds.split(",") if value.strip()]
    best_score: tuple[float, float, float] = (-1.0, -1.0, -1.0)
    best_epoch = 0
    best_loss = 0.0
    best_metrics: PeakMetrics | None = None
    patience_left = args.patience

    for epoch in range(1, args.epochs + 1):
        model.train()
        losses: list[float] = []
        for images, targets, _metas in train_loader:
            images = images.to(device)
            targets = targets.to(device)
            logits = model(images)
            weights = 1.0 + targets * args.positive_weight
            loss = functional.binary_cross_entropy_with_logits(logits, targets, weight=weights)
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            optimizer.step()
            losses.append(float(loss.detach().cpu().item()))

        metrics = evaluate_model(
            model,
            val_loader,
            device=device,
            width=args.input_width,
            height=args.input_height,
            radius_px=args.radius_px,
            thresholds=thresholds,
        )
        loss_value = statistics.mean(losses) if losses else 0.0
        score = (metrics.f1, metrics.recall, metrics.precision)
        print(
            f"epoch={epoch} loss={loss_value:.5f} "
            f"recall={metrics.recall:.3f} precision={metrics.precision:.3f} "
            f"f1={metrics.f1:.3f} threshold={metrics.threshold:.2f} oracle={metrics.oracle_recall:.3f}"
        )
        if score > best_score:
            best_score = score
            best_epoch = epoch
            best_loss = loss_value
            best_metrics = metrics
            patience_left = args.patience
            torch.save(
                {
                    "model_state": model.state_dict(),
                    "input_width": args.input_width,
                    "input_height": args.input_height,
                    "window": args.window,
                    "sigma": args.sigma,
                    "metrics": metrics.__dict__,
                },
                output_dir / "best.pt",
            )
        else:
            patience_left -= 1
            if patience_left <= 0:
                print(f"early_stop=1 epoch={epoch}")
                break

    torch.save(
        {
            "model_state": model.state_dict(),
            "input_width": args.input_width,
            "input_height": args.input_height,
            "window": args.window,
            "sigma": args.sigma,
        },
        output_dir / "last.pt",
    )
    if best_metrics is None:
        raise SystemExit("training finished without validation metrics")

    latency_ms = benchmark_latency(
        model,
        device=device,
        input_channels=args.window * 3,
        height=args.input_height,
        width=args.input_width,
        repeats=args.latency_repeats,
    )
    report = format_report(
        args=args,
        output_dir=output_dir,
        train_count=(
            real_train_count[0] + synthetic_count,
            real_train_count[1] + synthetic_count,
            real_train_count[2],
        ),
        real_train_count=real_train_count,
        synthetic_count=synthetic_count,
        val_count=summarize_samples(val_samples),
        best_epoch=best_epoch,
        best_loss=best_loss,
        best_metrics=best_metrics,
        latency_ms=latency_ms,
    )
    (output_dir / "report.md").write_text(report + "\n", encoding="utf-8")
    if args.output_markdown is not None:
        args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
        args.output_markdown.write_text(report + "\n", encoding="utf-8")
    print(report)
    return 0


def add_temporal_heatmap_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser_kwargs = {"formatter_class": argparse.ArgumentDefaultsHelpFormatter}
    temporal = subparsers.add_parser("temporal-heatmap", help="训练连续帧 heatmap 搜索 teacher。", **parser_kwargs)
    temporal_subparsers = temporal.add_subparsers(dest="temporal_command", required=True)

    train = temporal_subparsers.add_parser("train", help="训练 Search-S3 temporal heatmap teacher。", **parser_kwargs)
    train.add_argument("--images-root", type=Path, default=DEFAULT_IMAGES_ROOT, help="图片根目录")
    train.add_argument("--labels-root", type=Path, default=DEFAULT_LABELS_ROOT, help="YOLO 标签根目录")
    train.add_argument("--output-dir", type=Path, default=None, help="训练输出目录")
    train.add_argument("--output-markdown", type=Path, default=None, help="写入 Markdown 结果")
    train.add_argument("--name", default=DEFAULT_RUN_NAME, help="默认 run 名称")
    train.add_argument("--window", type=int, default=3, help="连续帧窗口，必须为奇数")
    train.add_argument("--input-width", type=int, default=640, help="网络输入宽度")
    train.add_argument("--input-height", type=int, default=360, help="网络输入高度")
    train.add_argument("--sigma", type=float, default=3.0, help="heatmap 高斯半径")
    train.add_argument("--radius-px", type=float, default=8.0, help="验证峰值距离阈值，输入尺度像素")
    train.add_argument("--train-include", default="", help="训练样本必须包含的逗号分隔 token；空表示不限制")
    train.add_argument("--train-exclude", default=DEFAULT_VAL_TOKEN, help="训练排除的逗号分隔 token")
    train.add_argument("--val-include", default=DEFAULT_VAL_TOKEN, help="验证包含的逗号分隔 token")
    train.add_argument("--max-negative-ratio", type=float, default=1.0, help="训练负样本最多为正样本的几倍")
    train.add_argument("--synthetic-count", type=int, default=0, help="额外在线合成 temporal 正样本数量")
    train.add_argument("--sprites-root", type=Path, default=DEFAULT_SPRITES_ROOT / "approved", help="合成样本使用的 approved sprite 目录")
    train.add_argument("--synthetic-sprite-scale-min", type=float, default=0.45, help="合成 sprite 最小缩放")
    train.add_argument("--synthetic-sprite-scale-max", type=float, default=1.35, help="合成 sprite 最大缩放")
    train.add_argument("--synthetic-motion-px-min", type=float, default=1.0, help="合成球每帧最小位移，输入尺度像素")
    train.add_argument("--synthetic-motion-px-max", type=float, default=16.0, help="合成球每帧最大位移，输入尺度像素")
    train.add_argument("--synthetic-blur-probability", type=float, default=0.25, help="合成 sprite 模糊概率")
    train.add_argument("--epochs", type=int, default=40, help="最大训练轮数")
    train.add_argument("--patience", type=int, default=10, help="验证 F1 无提升 early stop 轮数")
    train.add_argument("--batch", type=int, default=8, help="batch size")
    train.add_argument("--workers", type=int, default=2, help="DataLoader workers")
    train.add_argument("--threads", type=int, default=0, help="torch CPU 线程数；0 表示不修改")
    train.add_argument("--device", default="auto", help="cuda:0、cpu 或 auto")
    train.add_argument("--lr", type=float, default=1e-3, help="AdamW learning rate")
    train.add_argument("--weight-decay", type=float, default=1e-4, help="AdamW weight decay")
    train.add_argument("--positive-weight", type=float, default=80.0, help="heatmap 正区域 loss 权重")
    train.add_argument("--thresholds", default="0.05,0.10,0.15,0.20,0.30,0.40,0.50,0.60,0.70", help="验证阈值扫描")
    train.add_argument("--latency-repeats", type=int, default=30, help="训练后延迟测量次数")
    train.add_argument("--seed", type=int, default=20260704, help="随机种子")
    train.set_defaults(func=cmd_temporal_heatmap_train)

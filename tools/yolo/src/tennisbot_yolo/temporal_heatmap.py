from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime
import math
from pathlib import Path
import random
import re
import shutil
import statistics
import time
from typing import Any

from .dataset import IMAGE_SUFFIXES, format_yolo_box, read_yolo_labels, YoloBox
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
class TemporalPeakCandidate:
    sample: HeatmapSample
    score: float
    x_px: float
    y_px: float


@dataclass(frozen=True)
class PseudoTrack:
    track_id: int
    candidates: tuple[TemporalPeakCandidate, ...]


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
    motion_angle_deg_min: float
    motion_angle_deg_max: float
    center_x_min: float
    center_x_max: float
    center_y_min: float
    center_y_max: float
    blur_probability: float
    max_sprite_px: int


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


def build_mining_temporal_samples(
    *,
    images_root: Path,
    labels_root: Path,
    window: int,
    include_tokens: tuple[str, ...] = (),
    exclude_tokens: tuple[str, ...] = (),
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


def collect_synthetic_sprites(sprites_root: Path, exclude_tokens: tuple[str, ...] = ()) -> tuple[Path, ...]:
    if not sprites_root.exists():
        return ()
    sprites = [
        path
        for path in sorted(sprites_root.glob("*.png"))
        if path.is_file() and not path.name.endswith("_crop.png")
        and not any(token in path.name for token in exclude_tokens)
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


def bounded_center_range(*, limit: int, size: int, min_norm: float, max_norm: float) -> tuple[float, float]:
    fallback_min = size * 0.5
    fallback_max = max(fallback_min, limit - size * 0.5)
    lower = max(fallback_min, clamp_unit(min_norm) * limit)
    upper = min(fallback_max, clamp_unit(max_norm) * limit)
    if lower > upper:
        return fallback_min, fallback_max
    return lower, upper


def sample_motion_angle_degrees(rng: random.Random, min_deg: float, max_deg: float) -> float:
    if max_deg < min_deg:
        max_deg += 360.0
    return rng.uniform(min_deg, max_deg) % 360.0


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
        max_sprite_px = max(2, int(cfg.max_sprite_px))
        cap_scale = min(
            1.0,
            max_sprite_px / sprite_width,
            max_sprite_px / sprite_height,
            max(1, cfg.input_width - 2) / sprite_width,
            max(1, cfg.input_height - 2) / sprite_height,
        )
        if cap_scale < 1.0:
            sprite_width = max(1, int(round(sprite_width * cap_scale)))
            sprite_height = max(1, int(round(sprite_height * cap_scale)))
        sprite = cv2.resize(sprite, (sprite_width, sprite_height), interpolation=cv2.INTER_AREA)
        if cfg.blur_probability > 0.0 and rng.random() < cfg.blur_probability:
            kernel = rng.choice([3, 5, 7])
            sprite = cv2.GaussianBlur(sprite, (kernel, kernel), 0)

        max_x = max(0, cfg.input_width - sprite_width - 1)
        max_y = max(0, cfg.input_height - sprite_height - 1)
        center_x_min, center_x_max = bounded_center_range(
            limit=cfg.input_width,
            size=sprite_width,
            min_norm=cfg.center_x_min,
            max_norm=cfg.center_x_max,
        )
        center_y_min, center_y_max = bounded_center_range(
            limit=cfg.input_height,
            size=sprite_height,
            min_norm=cfg.center_y_min,
            max_norm=cfg.center_y_max,
        )
        center_x = rng.uniform(center_x_min, center_x_max)
        center_y = rng.uniform(center_y_min, center_y_max)
        motion = rng.uniform(cfg.motion_px_min, cfg.motion_px_max)
        angle = np.deg2rad(sample_motion_angle_degrees(rng, cfg.motion_angle_deg_min, cfg.motion_angle_deg_max))
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
    selection: str = "f1",
) -> PeakMetrics:
    if selection not in {"f1", "recall"}:
        raise ValueError("selection must be 'f1' or 'recall'")
    positives = sum(1 for prediction in predictions if prediction.positive)
    negatives = len(predictions) - positives
    oracle_hits = 0
    best: PeakMetrics | None = None
    best_key: tuple[float, float, float] | None = None
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
        if selection == "recall":
            key = (metric.recall, metric.precision, metric.f1)
        else:
            key = (metric.f1, metric.recall, metric.precision)
        if best_key is None or key > best_key:
            best_key = key
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
    selection: str = "f1",
) -> PeakMetrics:
    predictions = collect_predictions(model, loader, device=device, width=width, height=height)
    return compute_peak_metrics(
        predictions,
        width=width,
        height=height,
        radius_px=radius_px,
        thresholds=thresholds,
        selection=selection,
    )


def collect_peak_candidates(
    model: Any,
    samples: list[HeatmapSample],
    *,
    device: str,
    input_width: int,
    input_height: int,
    sigma: float,
    batch_size: int,
    workers: int,
) -> list[TemporalPeakCandidate]:
    import torch
    from torch.utils.data import DataLoader

    dataset = TemporalHeatmapDataset(
        samples=samples,
        input_width=input_width,
        input_height=input_height,
        sigma=sigma,
        augment=False,
    )
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False, num_workers=workers)
    candidates: list[TemporalPeakCandidate] = []
    sample_offset = 0
    model.eval()
    with torch.no_grad():
        for images, _targets, _metas in loader:
            images = images.to(device)
            heatmaps = torch.sigmoid(model(images)).detach().cpu()
            batch, _, heatmap_height, heatmap_width = heatmaps.shape
            flat = heatmaps.view(batch, -1)
            scores, indices = flat.max(dim=1)
            ys = torch.div(indices, heatmap_width, rounding_mode="floor").float()
            xs = (indices % heatmap_width).float()
            for index in range(batch):
                candidates.append(
                    TemporalPeakCandidate(
                        sample=samples[sample_offset + index],
                        score=float(scores[index].item()),
                        x_px=float(xs[index].item()),
                        y_px=float(ys[index].item()),
                    )
                )
            sample_offset += batch
    return candidates


def filter_temporal_tracks(
    candidates: list[TemporalPeakCandidate],
    *,
    min_score: float,
    min_track_length: int,
    max_frame_gap: int,
    max_motion_px: float,
) -> list[PseudoTrack]:
    if min_track_length <= 0:
        raise ValueError("min_track_length must be positive")
    if max_frame_gap <= 0:
        raise ValueError("max_frame_gap must be positive")
    if max_motion_px < 0:
        raise ValueError("max_motion_px must be non-negative")

    by_sequence: dict[str, list[TemporalPeakCandidate]] = {}
    for candidate in candidates:
        if candidate.score < min_score:
            continue
        by_sequence.setdefault(candidate.sample.sequence_key, []).append(candidate)

    tracks: list[PseudoTrack] = []
    next_track_id = 1
    for sequence_candidates in by_sequence.values():
        current: list[TemporalPeakCandidate] = []
        previous: TemporalPeakCandidate | None = None
        for candidate in sorted(sequence_candidates, key=lambda item: item.sample.frame_index):
            if previous is None:
                current = [candidate]
                previous = candidate
                continue
            frame_gap = candidate.sample.frame_index - previous.sample.frame_index
            distance = math.hypot(candidate.x_px - previous.x_px, candidate.y_px - previous.y_px)
            if 0 < frame_gap <= max_frame_gap and distance <= max_motion_px * frame_gap:
                current.append(candidate)
            else:
                if len(current) >= min_track_length:
                    tracks.append(PseudoTrack(next_track_id, tuple(current)))
                    next_track_id += 1
                current = [candidate]
            previous = candidate
        if len(current) >= min_track_length:
            tracks.append(PseudoTrack(next_track_id, tuple(current)))
            next_track_id += 1
    return tracks


def estimate_box_size(labels_root: Path, *, exclude_tokens: tuple[str, ...]) -> tuple[float, float]:
    widths: list[float] = []
    heights: list[float] = []
    for label_path in sorted(labels_root.rglob("*.txt")):
        haystack = label_path.relative_to(labels_root).as_posix()
        if exclude_tokens and any(token in haystack for token in exclude_tokens):
            continue
        for label in read_yolo_labels(label_path):
            widths.append(label.width)
            heights.append(label.height)
    if not widths or not heights:
        return 0.006, 0.011
    return statistics.median(widths), statistics.median(heights)


def copy_base_labels(base_labels_root: Path, output_labels_root: Path) -> int:
    copied = 0
    if not base_labels_root.exists():
        return copied
    for source in sorted(base_labels_root.rglob("*.txt")):
        target = output_labels_root / source.relative_to(base_labels_root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied += 1
    return copied


def clamp_unit(value: float) -> float:
    return max(0.0, min(1.0, value))


def write_pseudo_outputs(
    *,
    tracks: list[PseudoTrack],
    candidates: list[TemporalPeakCandidate],
    images_root: Path,
    base_labels_root: Path,
    output_root: Path,
    input_width: int,
    input_height: int,
    box_width: float,
    box_height: float,
    max_pseudo: int,
) -> dict[str, int]:
    output_labels_root = output_root / "labels"
    output_labels_root.mkdir(parents=True, exist_ok=True)
    copied_labels = copy_base_labels(base_labels_root, output_labels_root)

    track_lookup: dict[TemporalPeakCandidate, tuple[int, int]] = {}
    for track in tracks:
        for candidate in track.candidates:
            track_lookup[candidate] = (track.track_id, len(track.candidates))

    accepted = sorted(track_lookup, key=lambda candidate: (-candidate.score, candidate.sample.sequence_key, candidate.sample.frame_index))
    if max_pseudo > 0:
        accepted = accepted[:max_pseudo]
    accepted_set = set(accepted)

    manifest_path = output_root / "manifest.csv"
    candidates_path = output_root / "candidates.csv"
    written = 0
    skipped_existing = 0
    with manifest_path.open("w", encoding="utf-8", newline="") as manifest_file:
        manifest_writer = csv.writer(manifest_file)
        manifest_writer.writerow(
            [
                "image",
                "label",
                "sequence",
                "frame",
                "score",
                "x_center",
                "y_center",
                "box_width",
                "box_height",
                "track_id",
                "track_length",
            ]
        )
        for candidate in sorted(accepted, key=lambda item: (item.sample.sequence_key, item.sample.frame_index)):
            rel_image = candidate.sample.center_image.relative_to(images_root)
            rel_label = rel_image.with_suffix(".txt")
            label_path = output_labels_root / rel_label
            label_path.parent.mkdir(parents=True, exist_ok=True)
            if read_yolo_labels(label_path):
                skipped_existing += 1
                continue
            x_center = clamp_unit(candidate.x_px / max(1, input_width - 1))
            y_center = clamp_unit(candidate.y_px / max(1, input_height - 1))
            box = YoloBox(
                class_id=0,
                x_center=x_center,
                y_center=y_center,
                width=clamp_unit(box_width),
                height=clamp_unit(box_height),
            )
            label_path.write_text(format_yolo_box(box) + "\n", encoding="utf-8")
            track_id, track_length = track_lookup[candidate]
            manifest_writer.writerow(
                [
                    rel_image.as_posix(),
                    rel_label.as_posix(),
                    candidate.sample.sequence_key,
                    candidate.sample.frame_index,
                    f"{candidate.score:.6f}",
                    f"{x_center:.6f}",
                    f"{y_center:.6f}",
                    f"{box.width:.6f}",
                    f"{box.height:.6f}",
                    track_id,
                    track_length,
                ]
            )
            written += 1

    threshold_candidates = [candidate for candidate in candidates if candidate in track_lookup or candidate.score > 0.0]
    with candidates_path.open("w", encoding="utf-8", newline="") as candidates_file:
        writer = csv.writer(candidates_file)
        writer.writerow(["image", "sequence", "frame", "score", "x_px", "y_px", "status", "track_id", "track_length"])
        for candidate in sorted(threshold_candidates, key=lambda item: (item.sample.sequence_key, item.sample.frame_index)):
            rel_image = candidate.sample.center_image.relative_to(images_root)
            if candidate in accepted_set:
                track_id, track_length = track_lookup[candidate]
                status = "accepted"
            elif candidate in track_lookup:
                track_id, track_length = track_lookup[candidate]
                status = "max_pseudo_skipped"
            else:
                track_id, track_length = "", ""
                status = "track_rejected"
            writer.writerow(
                [
                    rel_image.as_posix(),
                    candidate.sample.sequence_key,
                    candidate.sample.frame_index,
                    f"{candidate.score:.6f}",
                    f"{candidate.x_px:.2f}",
                    f"{candidate.y_px:.2f}",
                    status,
                    track_id,
                    track_length,
                ]
            )

    return {
        "copied_labels": copied_labels,
        "tracks": len(tracks),
        "accepted_candidates": len(accepted),
        "written": written,
        "skipped_existing": skipped_existing,
    }


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
    best_recall_epoch: int,
    best_recall_loss: float,
    best_recall_metrics: PeakMetrics,
    latency_ms: float,
) -> str:
    distance = "" if best_metrics.mean_tp_distance is None else f"{best_metrics.mean_tp_distance:.2f}"
    recall_distance = (
        "" if best_recall_metrics.mean_tp_distance is None else f"{best_recall_metrics.mean_tp_distance:.2f}"
    )
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
            "### Best F1",
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
            "### Best Recall",
            "",
            "| epoch | loss | threshold | TP | FP | FN | recall | precision | F1 | oracle recall | mean TP dist px |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
            (
                f"| {best_recall_epoch} | {best_recall_loss:.5f} | {best_recall_metrics.threshold:.2f} | "
                f"{best_recall_metrics.tp} | {best_recall_metrics.fp} | {best_recall_metrics.fn} | "
                f"{best_recall_metrics.recall:.3f} | {best_recall_metrics.precision:.3f} | "
                f"{best_recall_metrics.f1:.3f} | {best_recall_metrics.oracle_recall:.3f} | {recall_distance} |"
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
        sprites = collect_synthetic_sprites(args.sprites_root.resolve(), exclude_tokens=val_include)
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
                motion_angle_deg_min=args.synthetic_motion_angle_deg_min,
                motion_angle_deg_max=args.synthetic_motion_angle_deg_max,
                center_x_min=args.synthetic_center_x_min,
                center_x_max=args.synthetic_center_x_max,
                center_y_min=args.synthetic_center_y_min,
                center_y_max=args.synthetic_center_y_max,
                blur_probability=args.synthetic_blur_probability,
                max_sprite_px=args.synthetic_max_sprite_px,
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
    best_recall_score: tuple[float, float, float] = (-1.0, -1.0, -1.0)
    best_epoch = 0
    best_loss = 0.0
    best_metrics: PeakMetrics | None = None
    best_recall_epoch = 0
    best_recall_loss = 0.0
    best_recall_metrics: PeakMetrics | None = None
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

        predictions = collect_predictions(
            model,
            val_loader,
            device=device,
            width=args.input_width,
            height=args.input_height,
        )
        metrics = compute_peak_metrics(
            predictions,
            width=args.input_width,
            height=args.input_height,
            radius_px=args.radius_px,
            thresholds=thresholds,
            selection="f1",
        )
        recall_metrics = compute_peak_metrics(
            predictions,
            width=args.input_width,
            height=args.input_height,
            radius_px=args.radius_px,
            thresholds=thresholds,
            selection="recall",
        )
        loss_value = statistics.mean(losses) if losses else 0.0
        score = (metrics.f1, metrics.recall, metrics.precision)
        recall_score = (recall_metrics.recall, recall_metrics.precision, recall_metrics.f1)
        improved = False
        print(
            f"epoch={epoch} loss={loss_value:.5f} "
            f"recall={metrics.recall:.3f} precision={metrics.precision:.3f} "
            f"f1={metrics.f1:.3f} threshold={metrics.threshold:.2f} oracle={metrics.oracle_recall:.3f} "
            f"best_recall={recall_metrics.recall:.3f}@{recall_metrics.threshold:.2f}"
        )
        if score > best_score:
            improved = True
            best_score = score
            best_epoch = epoch
            best_loss = loss_value
            best_metrics = metrics
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
        if recall_score > best_recall_score:
            improved = True
            best_recall_score = recall_score
            best_recall_epoch = epoch
            best_recall_loss = loss_value
            best_recall_metrics = recall_metrics
            torch.save(
                {
                    "model_state": model.state_dict(),
                    "input_width": args.input_width,
                    "input_height": args.input_height,
                    "window": args.window,
                    "sigma": args.sigma,
                    "metrics": recall_metrics.__dict__,
                },
                output_dir / "best_recall.pt",
            )
        if improved:
            patience_left = args.patience
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
    if best_recall_metrics is None:
        raise SystemExit("training finished without recall metrics")

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
        best_recall_epoch=best_recall_epoch,
        best_recall_loss=best_recall_loss,
        best_recall_metrics=best_recall_metrics,
        latency_ms=latency_ms,
    )
    (output_dir / "report.md").write_text(report + "\n", encoding="utf-8")
    if args.output_markdown is not None:
        args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
        args.output_markdown.write_text(report + "\n", encoding="utf-8")
    print(report)
    return 0


def cmd_temporal_heatmap_mine_pseudo(args: argparse.Namespace) -> int:
    import torch

    if args.batch <= 0:
        raise SystemExit("--batch must be positive")
    if args.max_samples < 0:
        raise SystemExit("--max-samples must be non-negative")

    checkpoint_path = args.checkpoint.resolve()
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    window = int(checkpoint.get("window", args.window or 0))
    input_width = int(checkpoint.get("input_width", args.input_width or 0))
    input_height = int(checkpoint.get("input_height", args.input_height or 0))
    sigma = float(checkpoint.get("sigma", args.sigma))
    if window <= 0 or window % 2 != 1:
        raise SystemExit("checkpoint does not define a valid odd window")
    if input_width <= 0 or input_height <= 0:
        raise SystemExit("checkpoint does not define valid input dimensions")

    device = args.device
    if device == "auto":
        device = "cuda:0" if torch.cuda.is_available() else "cpu"

    images_root = args.images_root.resolve()
    base_labels_root = args.base_labels_root.resolve()
    include_tokens = parse_token_list(args.include)
    exclude_tokens = parse_token_list(args.exclude)

    samples = build_mining_temporal_samples(
        images_root=images_root,
        labels_root=base_labels_root,
        window=window,
        include_tokens=include_tokens,
        exclude_tokens=exclude_tokens,
    )
    if args.max_samples:
        samples = samples[: args.max_samples]
    if not samples:
        raise SystemExit("no mining samples found")

    output_root = args.output_root
    if output_root is None:
        output_root = DEFAULT_RUNS_ROOT / "temporal_pseudo_labels" / args.name
    output_root = output_root.resolve()
    if output_root.exists():
        if not args.overwrite:
            raise SystemExit(f"output already exists: {output_root}")
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    box_width = float(args.box_width)
    box_height = float(args.box_height)
    if box_width <= 0.0 or box_height <= 0.0:
        box_width, box_height = estimate_box_size(base_labels_root, exclude_tokens=exclude_tokens)

    model = build_model(input_channels=window * 3)
    model.load_state_dict(checkpoint["model_state"])
    model.to(device)
    candidates = collect_peak_candidates(
        model,
        samples,
        device=device,
        input_width=input_width,
        input_height=input_height,
        sigma=sigma,
        batch_size=args.batch,
        workers=args.workers,
    )
    threshold_candidates = [candidate for candidate in candidates if candidate.score >= args.threshold]
    tracks = filter_temporal_tracks(
        candidates,
        min_score=args.threshold,
        min_track_length=args.min_track_length,
        max_frame_gap=args.max_frame_gap,
        max_motion_px=args.max_motion_px,
    )
    write_stats = write_pseudo_outputs(
        tracks=tracks,
        candidates=threshold_candidates,
        images_root=images_root,
        base_labels_root=base_labels_root,
        output_root=output_root,
        input_width=input_width,
        input_height=input_height,
        box_width=box_width,
        box_height=box_height,
        max_pseudo=args.max_pseudo,
    )

    report_lines = [
        f"# Temporal Pseudo-Label Mining Result - {datetime.now().strftime('%Y-%m-%d')}",
        "",
        "## Settings",
        "",
        f"- Checkpoint: `{checkpoint_path}`",
        f"- Output: `{output_root}`",
        f"- Images root: `{images_root}`",
        f"- Base labels root: `{base_labels_root}`",
        f"- Window: `{window}`",
        f"- Input: `{input_width}x{input_height}`",
        f"- Device: `{device}`",
        f"- Include tokens: `{args.include}`",
        f"- Exclude tokens: `{args.exclude}`",
        f"- Score threshold: `{args.threshold}`",
        f"- Min track length: `{args.min_track_length}`",
        f"- Max frame gap: `{args.max_frame_gap}`",
        f"- Max motion px/frame: `{args.max_motion_px}`",
        f"- Box size: `{box_width:.6f}x{box_height:.6f}`",
        "",
        "## Result",
        "",
        "| item | count |",
        "|---|---:|",
        f"| scanned windows | {len(samples)} |",
        f"| candidates above threshold | {len(threshold_candidates)} |",
        f"| accepted tracks | {write_stats['tracks']} |",
        f"| accepted candidates | {write_stats['accepted_candidates']} |",
        f"| copied base label files | {write_stats['copied_labels']} |",
        f"| written pseudo labels | {write_stats['written']} |",
        f"| skipped existing positives | {write_stats['skipped_existing']} |",
        "",
        "## Files",
        "",
        f"- Labels root: `{output_root / 'labels'}`",
        f"- Manifest: `{output_root / 'manifest.csv'}`",
        f"- Candidate audit: `{output_root / 'candidates.csv'}`",
    ]
    report = "\n".join(report_lines)
    (output_root / "report.md").write_text(report + "\n", encoding="utf-8")
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
    train.add_argument("--synthetic-motion-angle-deg-min", type=float, default=0.0, help="合成球运动角度最小值，0 向右、90 向下")
    train.add_argument("--synthetic-motion-angle-deg-max", type=float, default=360.0, help="合成球运动角度最大值，可小于最小值表示跨 360 度")
    train.add_argument("--synthetic-center-x-min", type=float, default=0.0, help="合成球中心 x 最小归一化位置")
    train.add_argument("--synthetic-center-x-max", type=float, default=1.0, help="合成球中心 x 最大归一化位置")
    train.add_argument("--synthetic-center-y-min", type=float, default=0.0, help="合成球中心 y 最小归一化位置")
    train.add_argument("--synthetic-center-y-max", type=float, default=1.0, help="合成球中心 y 最大归一化位置")
    train.add_argument("--synthetic-blur-probability", type=float, default=0.25, help="合成 sprite 模糊概率")
    train.add_argument("--synthetic-max-sprite-px", type=int, default=48, help="合成 sprite 输入尺度最大宽/高像素")
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

    mine = temporal_subparsers.add_parser("mine-pseudo", help="用 temporal heatmap teacher 挖掘带时序一致性过滤的伪标签。", **parser_kwargs)
    mine.add_argument("--checkpoint", type=Path, required=True, help="temporal heatmap checkpoint，通常使用 best_recall.pt")
    mine.add_argument("--images-root", type=Path, default=DEFAULT_IMAGES_ROOT, help="图片根目录")
    mine.add_argument("--base-labels-root", type=Path, default=DEFAULT_LABELS_ROOT, help="原始 YOLO 标签根目录，会复制到输出 labels")
    mine.add_argument("--output-root", type=Path, default=None, help="伪标签 run 输出目录")
    mine.add_argument("--output-markdown", type=Path, default=None, help="写入 Markdown 结果")
    mine.add_argument("--name", default=f"temporal_pseudo_{datetime.now().strftime('%Y%m%d')}", help="默认 run 名称")
    mine.add_argument("--include", default="", help="只挖掘包含这些逗号分隔 token 的图片")
    mine.add_argument("--exclude", default=DEFAULT_VAL_TOKEN, help="排除这些逗号分隔 token，默认排除验证序列")
    mine.add_argument("--threshold", type=float, default=0.70, help="teacher peak score 阈值")
    mine.add_argument("--min-track-length", type=int, default=3, help="至少连续多少个候选才写伪标签")
    mine.add_argument("--max-frame-gap", type=int, default=1, help="同一 track 相邻候选允许的最大帧间隔")
    mine.add_argument("--max-motion-px", type=float, default=48.0, help="输入尺度下同一 track 每帧最大位移")
    mine.add_argument("--max-pseudo", type=int, default=0, help="最多写多少个伪标签；0 表示不限")
    mine.add_argument("--max-samples", type=int, default=0, help="最多扫描多少个窗口；0 表示不限，用于快速试跑")
    mine.add_argument("--box-width", type=float, default=0.0, help="伪标签 box 归一化宽度；0 表示从真实标签估计")
    mine.add_argument("--box-height", type=float, default=0.0, help="伪标签 box 归一化高度；0 表示从真实标签估计")
    mine.add_argument("--window", type=int, default=0, help="checkpoint 缺少 window 时使用")
    mine.add_argument("--input-width", type=int, default=0, help="checkpoint 缺少 input_width 时使用")
    mine.add_argument("--input-height", type=int, default=0, help="checkpoint 缺少 input_height 时使用")
    mine.add_argument("--sigma", type=float, default=4.0, help="checkpoint 缺少 sigma 时使用")
    mine.add_argument("--batch", type=int, default=8, help="推理 batch size")
    mine.add_argument("--workers", type=int, default=4, help="DataLoader workers")
    mine.add_argument("--device", default="auto", help="cuda:0、cpu 或 auto")
    mine.add_argument("--overwrite", action="store_true", help="允许覆盖已有输出目录")
    mine.set_defaults(func=cmd_temporal_heatmap_mine_pseudo)

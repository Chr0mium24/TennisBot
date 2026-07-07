from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image

from .paths import REPO_ROOT

DEFAULT_MODEL_PATH = REPO_ROOT / "artifacts" / "models" / "tennis_ball_yolo" / "model.onnx"
MODEL_INPUT_SIZE = 1280
DEFAULT_CONFIDENCE = 0.05


@dataclass(frozen=True)
class Detection:
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float
    class_id: int = 0

    def as_dict(self) -> dict[str, float | int]:
        return {
            "x1": self.x1,
            "y1": self.y1,
            "x2": self.x2,
            "y2": self.y2,
            "confidence": self.confidence,
            "class_id": self.class_id,
        }


@dataclass(frozen=True)
class LetterboxInfo:
    scale: float
    pad_x: int
    pad_y: int
    width: int
    height: int


@lru_cache(maxsize=1)
def model_session(model_path: str = str(DEFAULT_MODEL_PATH)) -> ort.InferenceSession:
    return ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])


def clamp(value: float, low: float, high: float) -> float:
    return min(high, max(low, value))


def normalize_roi(roi: tuple[float, float, float, float], image_width: int, image_height: int) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = roi
    left = int(np.floor(clamp(min(x1, x2), 0, image_width - 1)))
    top = int(np.floor(clamp(min(y1, y2), 0, image_height - 1)))
    right = int(np.ceil(clamp(max(x1, x2), left + 1, image_width)))
    bottom = int(np.ceil(clamp(max(y1, y2), top + 1, image_height)))
    return left, top, right, bottom


def letterbox(image: Image.Image, size: int = MODEL_INPUT_SIZE) -> tuple[np.ndarray, LetterboxInfo]:
    width, height = image.size
    scale = min(size / max(width, 1), size / max(height, 1))
    resized_width = max(1, round(width * scale))
    resized_height = max(1, round(height * scale))
    resized = image.resize((resized_width, resized_height), Image.Resampling.BILINEAR)
    canvas = Image.new("RGB", (size, size), (114, 114, 114))
    pad_x = (size - resized_width) // 2
    pad_y = (size - resized_height) // 2
    canvas.paste(resized, (pad_x, pad_y))
    array = np.asarray(canvas, dtype=np.float32) / 255.0
    array = np.transpose(array, (2, 0, 1))[None]
    return array, LetterboxInfo(scale=scale, pad_x=pad_x, pad_y=pad_y, width=width, height=height)


def map_box_to_crop(row: np.ndarray, info: LetterboxInfo) -> tuple[float, float, float, float]:
    x1, y1, x2, y2 = [float(value) for value in row[:4]]
    x1 = (x1 - info.pad_x) / info.scale
    x2 = (x2 - info.pad_x) / info.scale
    y1 = (y1 - info.pad_y) / info.scale
    y2 = (y2 - info.pad_y) / info.scale
    return (
        clamp(x1, 0, info.width),
        clamp(y1, 0, info.height),
        clamp(x2, 0, info.width),
        clamp(y2, 0, info.height),
    )


def detect_tennis_ball(
    image_path: Path,
    roi: tuple[float, float, float, float] | None = None,
    confidence: float = DEFAULT_CONFIDENCE,
) -> list[Detection]:
    image = Image.open(image_path).convert("RGB")
    image_width, image_height = image.size
    if roi is None:
        left, top, right, bottom = 0, 0, image_width, image_height
    else:
        left, top, right, bottom = normalize_roi(roi, image_width, image_height)
    crop = image.crop((left, top, right, bottom))
    input_tensor, info = letterbox(crop)
    session = model_session()
    output = session.run(None, {session.get_inputs()[0].name: input_tensor})[0]
    rows = output[0] if output.ndim == 3 else output
    detections: list[Detection] = []
    for row in rows:
        score = float(row[4])
        if score < confidence:
            continue
        x1, y1, x2, y2 = map_box_to_crop(row, info)
        if x2 <= x1 or y2 <= y1:
            continue
        class_id = int(row[5]) if len(row) > 5 else 0
        detections.append(
            Detection(
                x1=x1 + left,
                y1=y1 + top,
                x2=x2 + left,
                y2=y2 + top,
                confidence=score,
                class_id=class_id,
            )
        )
    detections.sort(key=lambda item: item.confidence, reverse=True)
    return detections

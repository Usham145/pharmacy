from __future__ import annotations

import base64
import binascii
from functools import lru_cache
from pathlib import Path
from threading import Lock
from typing import Literal, TypedDict

import cv2
import numpy as np

MAX_IMAGE_BYTES = 6_000_000
MAX_IMAGE_PIXELS = 12_000_000
MODEL_INPUT_SIZE = 640
CONFIDENCE_THRESHOLD = 0.4
NMS_THRESHOLD = 0.2
MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "medicine_package_detector.onnx"
_inference_lock = Lock()


class ModelUnavailableError(RuntimeError):
    pass


class CandidateBox(TypedDict):
    x: int
    y: int
    width: int
    height: int
    confidence: float


class CountResult(TypedDict):
    count: int
    image_width: int
    image_height: int
    candidates: list[CandidateBox]
    method: Literal["yolov8n_onnx"]


@lru_cache(maxsize=1)
def _load_network() -> cv2.dnn.Net:
    if not MODEL_PATH.is_file():
        raise ModelUnavailableError(f"Trained package detector is missing: {MODEL_PATH}")
    try:
        return cv2.dnn.readNetFromONNX(str(MODEL_PATH))
    except cv2.error as error:
        raise ModelUnavailableError(f"Could not load trained package detector: {MODEL_PATH}") from error


def _parse_detections(
    output: np.ndarray,
    image_width: int,
    image_height: int,
    scale: float,
    pad_left: int,
    pad_top: int,
) -> list[CandidateBox]:
    predictions = np.asarray(output)
    if predictions.ndim == 3 and predictions.shape[0] == 1:
        predictions = predictions[0]
    if predictions.ndim != 2:
        raise RuntimeError(f"Unexpected detector output dimensions: {predictions.shape}")
    if predictions.shape[0] == 5:
        predictions = predictions.T
    if predictions.shape[1] != 5:
        raise RuntimeError(f"Expected 5 detector output values per package, got {predictions.shape}")

    boxes: list[list[int]] = []
    confidences: list[float] = []
    for center_x, center_y, width, height, confidence in predictions:
        score = float(confidence)
        if not np.isfinite(score) or not CONFIDENCE_THRESHOLD <= score <= 1:
            continue
        x1 = max(0, min(image_width, int(round((float(center_x) - float(width) / 2 - pad_left) / scale))))
        y1 = max(0, min(image_height, int(round((float(center_y) - float(height) / 2 - pad_top) / scale))))
        x2 = max(0, min(image_width, int(round((float(center_x) + float(width) / 2 - pad_left) / scale))))
        y2 = max(0, min(image_height, int(round((float(center_y) + float(height) / 2 - pad_top) / scale))))
        if x2 <= x1 or y2 <= y1:
            continue
        boxes.append([x1, y1, x2 - x1, y2 - y1])
        confidences.append(score)

    selected = (
        cv2.dnn.NMSBoxes(boxes, confidences, CONFIDENCE_THRESHOLD, NMS_THRESHOLD)
        if boxes
        else ()
    )
    indices = np.asarray(selected).reshape(-1) if selected is not None and len(selected) else []
    candidates = [
        {
            "x": boxes[int(index)][0],
            "y": boxes[int(index)][1],
            "width": boxes[int(index)][2],
            "height": boxes[int(index)][3],
            "confidence": round(confidences[int(index)], 4),
        }
        for index in indices
    ]
    candidates = [
        box for box in candidates
        if box["x"] > 0
        and box["y"] > 0
        and box["x"] + box["width"] < image_width
        and box["y"] + box["height"] < image_height
    ]
    candidates = _merge_adjacent_candidates(candidates)
    candidates.sort(key=lambda box: (box["y"], box["x"]))
    return candidates


def _merge_adjacent_candidates(candidates: list[CandidateBox]) -> list[CandidateBox]:
    merged: list[CandidateBox] = []
    for candidate in sorted(candidates, key=lambda box: box["confidence"], reverse=True):
        current = candidate.copy()
        index = 0
        while index < len(merged):
            previous = merged[index]
            overlap_x = max(
                0,
                min(previous["x"] + previous["width"], current["x"] + current["width"])
                - max(previous["x"], current["x"]),
            )
            overlap_y = max(
                0,
                min(previous["y"] + previous["height"], current["y"] + current["height"])
                - max(previous["y"], current["y"]),
            )
            overlap_x_ratio = overlap_x / min(previous["width"], current["width"])
            overlap_y_ratio = overlap_y / min(previous["height"], current["height"])
            if (
                overlap_x_ratio >= 0.65 and overlap_y_ratio >= 0.05
            ) or (
                overlap_y_ratio >= 0.65 and overlap_x_ratio >= 0.05
            ):
                left = min(previous["x"], current["x"])
                top = min(previous["y"], current["y"])
                right = max(
                    previous["x"] + previous["width"],
                    current["x"] + current["width"],
                )
                bottom = max(
                    previous["y"] + previous["height"],
                    current["y"] + current["height"],
                )
                current = {
                    "x": left,
                    "y": top,
                    "width": right - left,
                    "height": bottom - top,
                    "confidence": max(previous["confidence"], current["confidence"]),
                }
                merged.pop(index)
                index = 0
            else:
                index += 1
        merged.append(current)
    return merged


def _detect_packages(image: np.ndarray) -> list[CandidateBox]:
    image_height, image_width = image.shape[:2]
    scale = min(MODEL_INPUT_SIZE / image_width, MODEL_INPUT_SIZE / image_height)
    resized_width = int(round(image_width * scale))
    resized_height = int(round(image_height * scale))
    resized = cv2.resize(image, (resized_width, resized_height), interpolation=cv2.INTER_LINEAR)
    pad_width = MODEL_INPUT_SIZE - resized_width
    pad_height = MODEL_INPUT_SIZE - resized_height
    pad_left = pad_width // 2
    pad_right = pad_width - pad_left
    pad_top = pad_height // 2
    pad_bottom = pad_height - pad_top
    letterboxed = cv2.copyMakeBorder(
        resized,
        pad_top,
        pad_bottom,
        pad_left,
        pad_right,
        cv2.BORDER_CONSTANT,
        value=(114, 114, 114),
    )
    blob = cv2.dnn.blobFromImage(
        letterboxed,
        scalefactor=1 / 255,
        size=(MODEL_INPUT_SIZE, MODEL_INPUT_SIZE),
        swapRB=True,
        crop=False,
    )
    network = _load_network()
    with _inference_lock:
        network.setInput(blob)
        output = network.forward()
    return _parse_detections(output, image_width, image_height, scale, pad_left, pad_top)


def count_package_candidates(image_base64: str) -> CountResult:
    try:
        image_bytes = base64.b64decode(image_base64, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValueError("Image must be valid base64-encoded JPEG or PNG data") from error

    if not image_bytes or len(image_bytes) > MAX_IMAGE_BYTES:
        raise ValueError(f"Image must be between 1 byte and {MAX_IMAGE_BYTES} bytes")

    image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("OpenCV could not decode this image")

    image_height, image_width = image.shape[:2]
    if image_width * image_height > MAX_IMAGE_PIXELS:
        raise ValueError(f"Image dimensions must not exceed {MAX_IMAGE_PIXELS} pixels")

    candidates = _detect_packages(image)
    return {
        "count": len(candidates),
        "image_width": image_width,
        "image_height": image_height,
        "candidates": candidates,
        "method": "yolov8n_onnx",
    }

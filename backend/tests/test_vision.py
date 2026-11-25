from __future__ import annotations

import base64

import cv2
import numpy as np
import pytest

from app.services import vision
from app.services.barcodes import product_barcode_key


def encoded_image() -> str:
    image = np.full((480, 640, 3), 255, dtype=np.uint8)
    success, encoded = cv2.imencode(".jpg", image)
    assert success
    return base64.b64encode(encoded.tobytes()).decode("ascii")


class FakeNetwork:
    def setInput(self, _: np.ndarray) -> None:
        pass

    def forward(self) -> np.ndarray:
        return np.array(
            [[
                [100, 300, 100],
                [160, 160, 160],
                [60, 60, 60],
                [100, 100, 100],
                [0.91, 0.86, 0.72],
            ]],
            dtype=np.float32,
        )


def test_trained_detector_maps_boxes_back_to_image_and_suppresses_duplicates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(vision, "_load_network", lambda: FakeNetwork())

    result = vision.count_package_candidates(encoded_image())

    assert result["count"] == 2
    assert result["method"] == "yolov8n_onnx"
    assert result["candidates"][0] == {
        "x": 70,
        "y": 30,
        "width": 60,
        "height": 100,
        "confidence": 0.91,
    }
    assert result["candidates"][1]["x"] == 270
    assert result["candidates"][1]["y"] == 30


@pytest.mark.parametrize("image_base64", ["not-base64", ""])
def test_detector_rejects_invalid_image_data(image_base64: str) -> None:
    with pytest.raises(ValueError):
        vision.count_package_candidates(image_base64)


def test_detector_rejects_unexpected_model_output() -> None:
    with pytest.raises(RuntimeError, match="Unexpected detector output dimensions"):
        vision._parse_detections(np.zeros((2, 3, 4)), 640, 480, 1, 0, 80)


def test_adjacent_partial_boxes_from_one_blister_are_merged() -> None:
    merged = vision._merge_adjacent_candidates(
        [
            {"x": 50, "y": 50, "width": 100, "height": 120, "confidence": 0.91},
            {"x": 55, "y": 160, "width": 100, "height": 120, "confidence": 0.84},
        ]
    )

    assert merged == [
        {"x": 50, "y": 50, "width": 105, "height": 230, "confidence": 0.91}
    ]


def test_gs1_qr_and_ean_codes_normalize_to_the_same_product_identifier() -> None:
    ean = "4006381333931"
    gs1_element_string = "0104006381333931\x1d10LOT-A\x1d17260101"
    gs1_digital_link = "https://id.gs1.org/01/04006381333931/10/LOT-A/17/260101"

    expected = "04006381333931"
    assert product_barcode_key(ean) == expected
    assert product_barcode_key(gs1_element_string) == expected
    assert product_barcode_key(gs1_digital_link) == expected

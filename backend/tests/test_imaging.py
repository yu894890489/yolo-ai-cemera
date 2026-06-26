"""Tests for the JPEG crop helper used by the Consumer (BE-M1-B)."""

from __future__ import annotations

import numpy as np

from app.common import imaging


def _solid_jpeg_b64(width: int, height: int, color: int = 128) -> str:
    img = np.full((height, width, 3), color, dtype=np.uint8)
    return imaging.encode_jpeg_b64(img)


def test_encode_then_decode_roundtrips_shape():
    b64 = _solid_jpeg_b64(40, 30)
    img = imaging.decode_jpeg_b64(b64)
    assert img is not None
    assert img.shape == (30, 40, 3)


def test_crop_region_returns_subimage_within_bounds():
    b64 = _solid_jpeg_b64(100, 80)
    crop_b64 = imaging.crop_jpeg_b64(b64, [10, 20, 60, 70])
    assert crop_b64 is not None
    crop = imaging.decode_jpeg_b64(crop_b64)
    assert crop is not None
    # width 60-10=50, height 70-20=50
    assert crop.shape[0] == 50
    assert crop.shape[1] == 50


def test_crop_region_clamps_bbox_to_image_bounds():
    b64 = _solid_jpeg_b64(50, 50)
    crop_b64 = imaging.crop_jpeg_b64(b64, [-10, -10, 999, 999])
    crop = imaging.decode_jpeg_b64(crop_b64)
    assert crop is not None
    assert crop.shape[0] == 50
    assert crop.shape[1] == 50


def test_decode_invalid_base64_returns_none():
    assert imaging.decode_jpeg_b64("not-a-jpeg") is None
    assert imaging.decode_jpeg_b64("") is None


def test_crop_jpeg_b64_returns_none_on_invalid_input():
    assert imaging.crop_jpeg_b64("", [0, 0, 1, 1]) is None
    assert imaging.crop_jpeg_b64("garbage", [0, 0, 1, 1]) is None


def test_crop_jpeg_b64_returns_none_on_degenerate_bbox():
    b64 = _solid_jpeg_b64(50, 50)
    # zero-area bbox after clamping
    assert imaging.crop_jpeg_b64(b64, [60, 60, 70, 70]) is None

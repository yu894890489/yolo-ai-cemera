"""JPEG decode / crop / encode helpers for the small_crop path.

The Consumer decodes a frame once, crops the detection bbox (or ROI), and
forwards only the crop downstream so the full frame never lingers in memory or
travels through Redis. All functions are defensive: invalid input returns
``None`` rather than raising, so a malformed frame degrades a single alarm
instead of crashing the worker loop.
"""

from __future__ import annotations

import base64
import logging

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def decode_jpeg_b64(data: str) -> np.ndarray | None:
    if not data:
        return None
    try:
        raw = base64.b64decode(data, validate=False)
    except Exception:
        return None
    if not raw:
        return None
    buf = np.frombuffer(raw, dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if img is None or img.size == 0:
        return None
    return img


def encode_jpeg_b64(img: np.ndarray, quality: int = 85) -> str:
    ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
    if not ok:
        raise ValueError("jpeg encode failed")
    return base64.b64encode(buf.tobytes()).decode("ascii")


def crop_region(img: np.ndarray, bbox: list[int]) -> np.ndarray | None:
    """Crop ``img`` to ``bbox`` = [x1, y1, x2, y2], clamping to image bounds.

    Returns ``None`` when the clamped region has zero area.
    """
    if img is None or len(bbox) != 4:
        return None
    h, w = img.shape[:2]
    x1, y1, x2, y2 = (int(round(v)) for v in bbox)
    x1, x2 = sorted((x1, x2))
    y1, y2 = sorted((y1, y2))
    x1 = max(0, min(x1, w))
    x2 = max(0, min(x2, w))
    y1 = max(0, min(y1, h))
    y2 = max(0, min(y2, h))
    if x2 <= x1 or y2 <= y1:
        return None
    return img[y1:y2, x1:x2].copy()


def crop_jpeg_b64(frame_b64: str, bbox: list[int]) -> str | None:
    """Decode ``frame_b64``, crop ``bbox``, re-encode. ``None`` on any failure."""
    img = decode_jpeg_b64(frame_b64)
    if img is None:
        return None
    crop = crop_region(img, bbox)
    if crop is None:
        return None
    return encode_jpeg_b64(crop)

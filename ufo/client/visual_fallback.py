"""Small, dependency-free helpers for the UIA visual fallback path."""

from __future__ import annotations

import base64
import hashlib
import io
import json
from difflib import SequenceMatcher
from typing import Any, Iterable, Optional, Tuple


def screenshot_fingerprint(screenshot: Any) -> Optional[str]:
    """Return a stable fingerprint for a captured screenshot payload."""
    if not isinstance(screenshot, str) or not screenshot.startswith("data:image/"):
        return None

    payload = screenshot.partition(",")[2]
    try:
        raw = base64.b64decode(payload, validate=False)
    except Exception:
        raw = payload.encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def screenshot_changed(before: Any, after: Any) -> Optional[bool]:
    """Compare screenshots, returning ``None`` when either capture is invalid."""
    before_fingerprint = screenshot_fingerprint(before)
    after_fingerprint = screenshot_fingerprint(after)
    if before_fingerprint is None or after_fingerprint is None:
        return None
    return before_fingerprint != after_fingerprint


def build_visual_locator_messages(
    screenshot_data: str, target_name: str
) -> list[dict[str, Any]]:
    """Build a vision request using the same OpenAI-compatible image format as UFO agents."""
    return [
        {
            "role": "system",
            "content": (
                "You locate visible UI targets in screenshots. Return only a JSON object "
                'with keys "found", "x", and "y". If the named target is visible, '
                "set found to true and give the center point as normalized fractions "
                "from 0.0 to 1.0 of the screenshot width and height. If not visible, "
                'return {"found": false}. Do not guess when uncertain.'
            ),
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": f"Locate this visible UI target: {target_name}",
                },
                {"type": "image_url", "image_url": {"url": screenshot_data}},
            ],
        },
    ]


def parse_visual_location(response: Any) -> Optional[dict[str, float]]:
    """Parse a Qwen locator response and reject missing or out-of-window points."""
    if not isinstance(response, str):
        return None

    text = response.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text[:4].lower() == "json":
            text = text[4:].strip()

    try:
        payload = json.loads(text)
    except (TypeError, ValueError):
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            payload = json.loads(text[start : end + 1])
        except (TypeError, ValueError):
            return None

    if not isinstance(payload, dict) or payload.get("found") is not True:
        return None

    try:
        x, y = float(payload["x"]), float(payload["y"])
    except (KeyError, TypeError, ValueError):
        return None
    if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
        return None
    return {"x": x, "y": y}


def locate_with_vision_model(
    screenshot_data: str,
    target_name: str,
    completion: Any,
) -> Optional[dict[str, float]]:
    """Request a visual target point from the caller's configured vision model."""
    if not isinstance(screenshot_data, str) or not screenshot_data.startswith(
        "data:image/"
    ):
        return None
    messages = build_visual_locator_messages(screenshot_data, target_name)
    response = completion(messages)
    if isinstance(response, tuple):
        response = response[0]
    if isinstance(response, list):
        response = response[0] if response else None
    return parse_visual_location(response)


def screenshot_point_to_window_fraction(
    screenshot_data: str,
    point: dict[str, float],
    window_width: float,
    window_height: float,
) -> Optional[dict[str, float]]:
    """Convert normalized screenshot coordinates to window-relative fractions."""
    if window_width <= 0 or window_height <= 0:
        return None
    if not isinstance(screenshot_data, str) or not screenshot_data.startswith(
        "data:image/"
    ):
        return None
    try:
        from PIL import Image

        payload = screenshot_data.partition(",")[2]
        image = Image.open(io.BytesIO(base64.b64decode(payload)))
        screenshot_width, screenshot_height = image.size
    except Exception:
        return None
    if screenshot_width <= 0 or screenshot_height <= 0:
        return None

    try:
        x = float(point["x"]) * screenshot_width / window_width
        y = float(point["y"]) * screenshot_height / window_height
    except (KeyError, TypeError, ValueError):
        return None
    if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
        return None
    return {"x": x, "y": y}


def _candidate_name(candidate: Any) -> str:
    if isinstance(candidate, dict):
        return str(candidate.get("name") or candidate.get("content") or "")
    return str(getattr(candidate, "name", "") or "")


def _candidate_rect(candidate: Any) -> Optional[Tuple[float, float, float, float]]:
    rect = candidate.get("rect") if isinstance(candidate, dict) else getattr(candidate, "rect", None)
    if not rect or len(rect) < 4:
        return None
    try:
        left, top, right, bottom = (float(value) for value in rect[:4])
    except (TypeError, ValueError):
        return None
    if right <= left or bottom <= top:
        return None
    return left, top, right, bottom


def rank_visual_candidates(
    requested_name: str, candidates: Iterable[Any]
) -> list[tuple[float, Any]]:
    """Rank visual candidates without selecting unrelated controls."""
    wanted = " ".join(str(requested_name or "").lower().split())
    if not wanted:
        return []

    ranked: list[tuple[float, Any]] = []
    for candidate in candidates or []:
        name = " ".join(_candidate_name(candidate).lower().split())
        if not name:
            continue

        if name == wanted:
            score = 1.0
        elif wanted in name or name in wanted:
            score = 0.85
        else:
            score = SequenceMatcher(None, wanted, name).ratio()
            if score < 0.72:
                continue
        if _candidate_rect(candidate) is not None:
            ranked.append((score, candidate))

    return sorted(ranked, key=lambda item: item[0], reverse=True)


def rect_center_to_relative(
    rect: Iterable[float], application_rect: Iterable[float]
) -> Optional[Tuple[float, float]]:
    """Convert an absolute rectangle center to app-window fractional coordinates."""
    try:
        left, top, right, bottom = (float(value) for value in list(rect)[:4])
        app_left, app_top, app_right, app_bottom = (
            float(value) for value in list(application_rect)[:4]
        )
    except (TypeError, ValueError):
        return None

    app_width = app_right - app_left
    app_height = app_bottom - app_top
    if app_width <= 0 or app_height <= 0 or right <= left or bottom <= top:
        return None

    x = ((left + right) / 2.0 - app_left) / app_width
    y = ((top + bottom) / 2.0 - app_top) / app_height
    if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
        return None
    return x, y


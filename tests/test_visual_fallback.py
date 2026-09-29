from ufo.client.visual_fallback import (
    build_visual_locator_messages,
    locate_with_vision_model,
    parse_visual_location,
    rank_visual_candidates,
    rect_center_to_relative,
    screenshot_point_to_window_fraction,
    screenshot_changed,
)


def test_visual_candidates_prefer_exact_name():
    candidates = [
        {"name": "Submit form", "rect": [100, 100, 200, 140]},
        {"name": "Submit", "rect": [300, 100, 380, 140]},
    ]

    ranked = rank_visual_candidates("Submit", candidates)

    assert ranked[0][1]["name"] == "Submit"
    assert ranked[0][0] == 1.0


def test_rect_center_is_converted_to_application_fraction():
    assert rect_center_to_relative([120, 240, 220, 340], [100, 200, 500, 600]) == (
        0.175,
        0.225,
    )


def test_screenshot_changed_distinguishes_valid_payloads():
    before = "data:image/png;base64,YQ=="
    after = "data:image/png;base64,Yg=="

    assert screenshot_changed(before, after) is True
    assert screenshot_changed(before, before) is False
    assert screenshot_changed("Error: capture failed", after) is None


def test_visual_locator_prompt_passes_screenshot_and_target_to_configured_vision_model():
    messages = build_visual_locator_messages(
        "data:image/png;base64,ZmFrZQ==", "文字"
    )

    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert messages[1]["content"][0]["type"] == "text"
    assert "文字" in messages[1]["content"][0]["text"]
    assert messages[1]["content"][1] == {
        "type": "image_url",
        "image_url": {"url": "data:image/png;base64,ZmFrZQ=="},
    }


def test_visual_locator_parses_and_bounds_normalized_coordinates():
    assert parse_visual_location('{"found": true, "x": 0.25, "y": 0.75}') == {
        "x": 0.25,
        "y": 0.75,
    }
    assert parse_visual_location('{"found": false}') is None
    assert parse_visual_location('{"found": true, "x": 2, "y": 0.5}') is None
    assert parse_visual_location("not json") is None


def test_visual_locator_calls_injected_vision_completion_with_image():
    observed = {}

    def completion(messages):
        observed["messages"] = messages
        return ['{"found": true, "x": 0.4, "y": 0.6}'], 0.0

    result = locate_with_vision_model(
        "data:image/png;base64,ZmFrZQ==", "Save", completion
    )

    assert result == {"x": 0.4, "y": 0.6}
    assert observed["messages"][1]["content"][1]["image_url"]["url"].startswith(
        "data:image/"
    )


def test_screenshot_point_is_scaled_to_window_dimensions():
    import base64
    import io

    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (200, 100)).save(buffer, format="PNG")
    screenshot = "data:image/png;base64," + base64.b64encode(
        buffer.getvalue()
    ).decode("ascii")

    assert screenshot_point_to_window_fraction(
        screenshot, {"x": 0.5, "y": 0.5}, 100, 100
    ) == {"x": 1.0, "y": 0.5}


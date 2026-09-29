from types import SimpleNamespace

from ufo.client.mcp.local_servers.ui_mcp_server import (
    _capture_selected_window_screenshot,
)


class _FakePhotographer:
    def capture_app_window_screenshot(self, _window):
        return SimpleNamespace(size=(100, 100))

    def capture_desktop_screen_screenshot(self, all_screens=False):
        assert all_screens is False
        return SimpleNamespace(size=(100, 100))

    def encode_image(self, _screenshot):
        return "data:image/png;base64,ZmFrZQ=="


def test_visual_locator_can_capture_from_shared_screenshot_helper():
    state = SimpleNamespace(
        selected_app_window=object(), photographer=_FakePhotographer()
    )

    result = _capture_selected_window_screenshot(state)

    assert result.startswith("data:image/")


def test_visual_locator_reports_missing_selected_window():
    state = SimpleNamespace(
        selected_app_window=None, photographer=_FakePhotographer()
    )

    assert _capture_selected_window_screenshot(state) == "Error: No window selected"

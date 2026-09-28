import unittest

from ufo.automator.ui_control.controller import ControlReceiver


class _ScrollPattern:
    CurrentVerticallyScrollable = True
    CurrentVerticalScrollPercent = 0.0
    CurrentVerticalViewSize = 20.0

    def __init__(self):
        self.calls = []

    def SetScrollPercent(self, horizontal, vertical):
        self.calls.append((horizontal, vertical))
        self.CurrentVerticalScrollPercent = vertical


class _Control:
    def __init__(self, pattern):
        self.iface_scroll = pattern


class ScreenshotScrollOverlapTests(unittest.TestCase):
    def test_scroll_uses_viewport_size_to_keep_ten_percent_overlap(self):
        pattern = _ScrollPattern()
        receiver = ControlReceiver.__new__(ControlReceiver)
        receiver.control = _Control(pattern)
        receiver.application = None

        result = receiver.wheel_mouse_input(
            {"wheel_dist": -20, "overlap_ratio": 0.1}
        )

        self.assertEqual(pattern.calls, [(-1.0, 18.0)])
        self.assertIn("before=0.0", result)
        self.assertIn("after=18.0", result)


if __name__ == "__main__":
    unittest.main()

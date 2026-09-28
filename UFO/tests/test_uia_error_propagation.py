import importlib
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace


def _load_controller_with_lightweight_windows_stubs():
    """Load the controller without requiring pywinauto on the test runner."""
    if "ufo.automator.ui_control.controller" in sys.modules:
        return sys.modules["ufo.automator.ui_control.controller"]

    pyautogui = types.ModuleType("pyautogui")
    pyautogui.FAILSAFE = False
    pywinauto = types.ModuleType("pywinauto")
    pywinauto.timings = SimpleNamespace(Timings=SimpleNamespace())
    pywinauto.keyboard = SimpleNamespace(send_keys=lambda *_args, **_kwargs: None)
    pywinauto_controls = types.ModuleType("pywinauto.controls")
    pywinauto_uia = types.ModuleType("pywinauto.controls.uiawrapper")
    pywinauto_uia.UIAWrapper = object
    pywinauto_structures = types.ModuleType("pywinauto.win32structures")
    pywinauto_structures.RECT = object
    pywinauto.controls = pywinauto_controls
    pywinauto_controls.uiawrapper = pywinauto_uia
    sys.modules.update(
        {
            "pyautogui": pyautogui,
            "pywinauto": pywinauto,
            "pywinauto.controls": pywinauto_controls,
            "pywinauto.controls.uiawrapper": pywinauto_uia,
            "pywinauto.win32structures": pywinauto_structures,
        }
    )

    config_loader = types.ModuleType("config.config_loader")
    config_loader.get_ufo_config = lambda: SimpleNamespace(
        system=SimpleNamespace(
            after_click_wait=0,
            click_api="click_input",
            input_text_inter_key_pause=0.0,
            input_text_api="type_keys",
            input_text_enter=False,
            default_png_compress_level=1,
            annotation_colors={},
            annotation_font_size=12,
        )
    )
    sys.modules["config.config_loader"] = config_loader

    repository_root = Path(__file__).resolve().parent.parent
    automator_package = types.ModuleType("ufo.automator")
    automator_package.__path__ = [str(repository_root / "ufo" / "automator")]
    ui_control_package = types.ModuleType("ufo.automator.ui_control")
    ui_control_package.__path__ = [
        str(repository_root / "ufo" / "automator" / "ui_control")
    ]
    sys.modules["ufo.automator"] = automator_package
    sys.modules["ufo.automator.ui_control"] = ui_control_package

    puppeteer = types.ModuleType("ufo.automator.puppeteer")

    class ReceiverManager:
        @classmethod
        def register(cls, factory):
            return factory

    puppeteer.ReceiverManager = ReceiverManager
    sys.modules["ufo.automator.puppeteer"] = puppeteer

    return importlib.import_module("ufo.automator.ui_control.controller")


class UiaErrorPropagationTests(unittest.TestCase):
    def setUp(self):
        self._modules_before_test = dict(sys.modules)

    def tearDown(self):
        for module_name in list(sys.modules):
            if module_name not in self._modules_before_test:
                del sys.modules[module_name]
        for module_name, module in self._modules_before_test.items():
            sys.modules[module_name] = module

    def test_click_input_raises_when_uia_operation_reports_error(self):
        controller = _load_controller_with_lightweight_windows_stubs()
        receiver = object.__new__(controller.ControlReceiver)
        receiver.control = object()
        receiver.application = object()
        receiver.atomic_execution = lambda *_args, **_kwargs: (
            "An error occurred: stale UIA control"
        )

        with self.assertRaisesRegex(RuntimeError, "stale UIA control"):
            receiver.click_input({})


if __name__ == "__main__":
    unittest.main()

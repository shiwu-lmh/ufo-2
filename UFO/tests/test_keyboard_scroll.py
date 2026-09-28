import unittest
from unittest.mock import patch

from ufo.automator.ui_control import controller as controller_module
from ufo.automator.ui_control.controller import ControlReceiver, TextTransformer


class KeyboardScrollTests(unittest.TestCase):
    def test_page_down_alias_is_normalized_to_pywinauto_key_name(self):
        self.assertEqual(
            TextTransformer.transform_text("{PAGE_DOWN}", "all"), "{PGDN}{UP 5}"
        )


    def test_keyboard_input_does_not_report_success_after_executor_failure(self):
        receiver = ControlReceiver.__new__(ControlReceiver)
        receiver.control = type(
            "FailingControl", (), {"set_focus": lambda self: None}
        )()
        receiver.application = None
        receiver.atomic_execution = lambda *_args, **_kwargs: (
            "An error occurred: Unknown code: PAGE_DOWN"
        )

        with patch.object(controller_module.pyautogui, "write"):
            with self.assertRaisesRegex(RuntimeError, "Unknown code: PAGE_DOWN"):
                receiver.keyboard_input({"keys": "{PAGE_DOWN}"})

    def test_page_navigation_focuses_document_before_typing_to_application(self):
        document = _FocusableDocument()
        application = _ApplicationWithDocument(document)
        receiver = ControlReceiver.__new__(ControlReceiver)
        receiver.control = object()
        receiver.application = application

        receiver.keyboard_input({"keys": "{PAGE_DOWN}", "control_focus": False})

        self.assertEqual(
            application.calls, ["set_focus", "type_keys:{PGDN}{UP 5}"]
        )
        self.assertEqual(document.calls, ["set_focus"])


class _FocusableDocument:
    def __init__(self):
        self.calls = []

    def is_visible(self):
        return True

    def is_enabled(self):
        return True

    def set_focus(self):
        self.calls.append("set_focus")


class _ApplicationWithDocument:
    def __init__(self, document):
        self.document = document
        self.calls = []

    def descendants(self, **kwargs):
        return [self.document]

    def set_focus(self):
        self.calls.append("set_focus")

    def type_keys(self, **kwargs):
        self.calls.append(f"type_keys:{kwargs['keys']}")
        return ""

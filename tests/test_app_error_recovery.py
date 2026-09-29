"""Regression tests for AppAgent warnings seen in desktop_3 execution logs."""

import logging
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from aip.messages import Result, ResultStatus

# Import the processor first to mirror the application's normal module loading order.
import ufo.agents.processors.app_agent_processor  # noqa: F401
from ufo.agents.processors.schemas.actions import ActionCommandInfo
from ufo.agents.processors.strategies.app_agent_processing_strategy import (
    AppActionExecutionStrategy,
    AppControlInfoStrategy,
    AppLLMInteractionStrategy,
    AppScreenshotCaptureStrategy,
)


def test_app_llm_declares_the_result_field_it_returns():
    """The response schema's optional result must be part of the provides contract."""
    assert "result" in AppLLMInteractionStrategy().get_provides()


def test_empty_action_is_removed_before_result_alignment():
    """A model FINISH with no function must not create a fake result mismatch."""
    strategy = AppActionExecutionStrategy()

    action_info = strategy._create_action_info(
        annotation_dict={},
        actions=ActionCommandInfo(function="", status="FINISH"),
        execution_results=[],
    )

    assert action_info == []


class AppErrorRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_window_info_stops_data_collection_cleanly(self):
        """A stale HWND must stop before the UIA strategy receives a null window."""
        strategy = AppScreenshotCaptureStrategy()
        strategy._capture_app_screenshot = AsyncMock(return_value="empty")
        strategy._get_application_window_info = AsyncMock(return_value=None)
        context = SimpleNamespace(
            get=lambda key, default=None: {
                "log_path": "logs/",
                "session_step": 1,
            }.get(key, default),
            global_context=SimpleNamespace(command_dispatcher=object()),
        )

        result = await strategy.execute(agent=None, context=context)

        self.assertFalse(result.success)
        self.assertIn("Application window info unavailable", result.error)

    async def test_none_uia_result_is_reported_as_empty_controls(self):
        """A lost selected window should not emit a NoneType length traceback."""
        strategy = AppControlInfoStrategy()
        dispatcher = AsyncMock(
            execute_commands=AsyncMock(
                return_value=[Result(status=ResultStatus.SUCCESS, result=None)]
            )
        )

        with self.assertLogs(level=logging.WARNING) as captured:
            controls = await strategy._collect_uia_controls(dispatcher)

        self.assertEqual(controls, [])
        self.assertNotIn(
            "object of type 'NoneType' has no len()", "\n".join(captured.output)
        )

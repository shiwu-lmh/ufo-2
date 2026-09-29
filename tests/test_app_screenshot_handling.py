"""Regression tests for automatic screenshot requests from AppAgent responses."""

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from aip.messages import Result, ResultStatus
import yaml

from ufo.agents.processors.schemas.actions import ActionCommandInfo
# Import the processor first to mirror the application's normal module loading order.
import ufo.agents.processors.app_agent_processor  # noqa: F401
from ufo.agents.processors.strategies.app_agent_processing_strategy import (
    AppActionExecutionStrategy,
    AppScreenshotCaptureStrategy,
)


class AutomaticScreenshotActionTests(unittest.IsolatedAsyncioTestCase):
    async def test_save_screenshot_marker_is_not_sent_to_ui_tools(self):
        """The response metadata field must not become an unregistered UI action."""
        strategy = AppActionExecutionStrategy()
        dispatcher = AsyncMock()
        action = ActionCommandInfo(function="save_screenshot", status="FINISH")

        results = await strategy._execute_app_action(dispatcher, action)

        dispatcher.execute_commands.assert_not_awaited()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, ResultStatus.SUCCESS)

    async def test_real_ui_action_is_still_sent_to_ui_tools(self):
        strategy = AppActionExecutionStrategy()
        dispatcher = AsyncMock(
            execute_commands=AsyncMock(
                return_value=[Result(status=ResultStatus.SUCCESS, result="clicked")]
            )
        )
        action = ActionCommandInfo(
            function="click_input",
            arguments={"id": "9", "name": "我喜欢的音乐"},
            status="CONTINUE",
        )

        results = await strategy._execute_app_action(dispatcher, action)

        dispatcher.execute_commands.assert_awaited_once()
        command = dispatcher.execute_commands.await_args.args[0][0]
        self.assertEqual(command.tool_name, "click_input")
        self.assertEqual(results[0].status, ResultStatus.SUCCESS)

    async def test_screenshot_marker_preserves_the_order_of_real_ui_actions(self):
        strategy = AppActionExecutionStrategy()
        dispatcher = AsyncMock(
            execute_commands=AsyncMock(
                return_value=[Result(status=ResultStatus.SUCCESS, result="clicked")]
            )
        )
        actions = [
            ActionCommandInfo(function="save_screenshot", status="CONTINUE"),
            ActionCommandInfo(function="click_input", status="FINISH"),
        ]

        results = await strategy._execute_app_action(dispatcher, actions)

        command = dispatcher.execute_commands.await_args.args[0][0]
        self.assertEqual(command.tool_name, "click_input")
        self.assertEqual(
            results[0].result,
            "Screenshot saving is handled automatically by UFO; "
            "the current snapshot has been recorded.",
        )
        self.assertEqual(results[1].result, "clicked")


class ClosedWindowRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_closed_window_hands_control_back_without_capturing_stale_handle(self):
        dispatcher = AsyncMock(
            execute_commands=AsyncMock(
                return_value=[Result(status=ResultStatus.SUCCESS, result=None)]
            )
        )
        local_context = SimpleNamespace(
            status=None,
            result="",
            comment="",
            application_window_info=object(),
            custom_data={},
        )
        context = SimpleNamespace(
            global_context=SimpleNamespace(
                command_dispatcher=dispatcher,
                set=lambda *_args: None,
            ),
            local_context=local_context,
            get=lambda key, default=None: {
                "log_path": "logs/test/",
                "session_step": 3,
            }.get(key, default),
            get_local=lambda key, default=None: getattr(local_context, key, default),
            set_local=lambda key, value: setattr(local_context, key, value),
        )
        agent = SimpleNamespace(
            memory=SimpleNamespace(
                filter_memory_from_keys=lambda _keys: [
                    {
                        "action": [
                            {
                                "function": "click_input",
                                "arguments": {"name": "关闭"},
                                "result": {"status": "success"},
                            }
                        ]
                    }
                ]
            )
        )

        result = await AppScreenshotCaptureStrategy().execute(agent, context)

        self.assertTrue(result.success)
        self.assertTrue(result.data["stop_processing"])
        self.assertEqual(local_context.status, "FINISH")
        self.assertIn("refresh the window list", local_context.result)
        self.assertEqual(dispatcher.execute_commands.await_count, 1)
        self.assertEqual(
            dispatcher.execute_commands.await_args.args[0][0].tool_name,
            "get_app_window_info",
        )

class TaskFidelityConfigurationTests(unittest.TestCase):
    _repository_root = Path(__file__).resolve().parent.parent

    def test_host_uses_the_stronger_vision_model_for_task_planning(self):
        config = yaml.safe_load(
            (self._repository_root / "config" / "ufo" / "agents.yaml").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(config["HOST_AGENT"]["API_MODEL"], "qwen3.8-flash")

    def test_prompts_preserve_named_user_targets_and_end_after_verification(self):
        prompt_paths = {
            "host": self._repository_root
            / "ufo"
            / "prompts"
            / "share"
            / "base"
            / "host_agent.yaml",
            "app": self._repository_root
            / "ufo"
            / "prompts"
            / "share"
            / "base"
            / "app_agent.yaml",
        }

        for agent_kind, prompt_path in prompt_paths.items():
            with self.subTest(prompt=prompt_path.name):
                prompt = yaml.safe_load(prompt_path.read_text(encoding="utf-8"))["system"]
                self.assertIn("Never replace a named destination", prompt)
                self.assertIn("set status to FINISH", prompt)
                if agent_kind == "host":
                    self.assertIn("When opening NetEase Cloud Music", prompt)

    def test_prompts_require_all_requested_calculations_and_truthful_results(self):
        host_prompt = yaml.safe_load(
            (
                self._repository_root
                / "ufo"
                / "prompts"
                / "share"
                / "base"
                / "host_agent.yaml"
            ).read_text(encoding="utf-8")
        )["system"]
        app_prompt = yaml.safe_load(
            (
                self._repository_root
                / "ufo"
                / "prompts"
                / "share"
                / "base"
                / "app_agent.yaml"
            ).read_text(encoding="utf-8")
        )["system"]

        self.assertIn("sum or total, assign a separate calculator sub-task", host_prompt)
        self.assertIn("observed result differs from the expected result", app_prompt)
        self.assertIn("Never report PASS", app_prompt)


if __name__ == "__main__":
    unittest.main()

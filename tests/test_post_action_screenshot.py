import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from ufo.agents.processors.core import processor_framework  # noqa: F401
from ufo.agents.processors.schemas.actions import ActionCommandInfo
from ufo.agents.processors.strategies.app_agent_processing_strategy import (
    AppActionExecutionStrategy,
)


class _FakeDispatcher:
    def __init__(self, frames):
        self.frames = iter(frames)
        self.calls = 0

    async def execute_commands(self, _commands):
        self.calls += 1
        return [
            SimpleNamespace(
                status="success",
                result=next(self.frames),
            )
        ]


class PostActionScreenshotTests(unittest.IsolatedAsyncioTestCase):
    async def test_stable_capture_saves_only_after_two_matching_frames(self):
        strategy = AppActionExecutionStrategy()
        dispatcher = _FakeDispatcher(
            [
                "data:image/png;base64,frame1",
                "data:image/png;base64,frame2",
                "data:image/png;base64,frame2",
            ]
        )
        fake_image = SimpleNamespace(size=(100, 100))

        with patch(
            "ufo.agents.processors.strategies.app_agent_processing_strategy.utils.save_image_string",
            return_value=fake_image,
        ) as save_image, patch(
            "ufo.agents.processors.strategies.app_agent_processing_strategy.asyncio.sleep",
            new_callable=AsyncMock,
        ) as sleep:
            result = await strategy._capture_stable_app_screenshot(
                "after_action.png", dispatcher
            )

        self.assertTrue(result)
        self.assertEqual(dispatcher.calls, 3)
        self.assertEqual(save_image.call_args.args, ("data:image/png;base64,frame2", "after_action.png"))
        sleep.assert_any_await(1.2)

    def test_screenshot_request_with_action_requires_post_action_refresh(self):
        strategy = AppActionExecutionStrategy()
        response = SimpleNamespace(
            action=ActionCommandInfo(function="keyboard_input"),
            save_screenshot={"save": True},
        )

        self.assertTrue(strategy._should_capture_post_action_screenshot(response))

    def test_scroll_action_requires_post_action_refresh_without_metadata(self):
        strategy = AppActionExecutionStrategy()
        response = SimpleNamespace(
            action=ActionCommandInfo(
                function="keyboard_input",
                arguments={"keys": "{PAGE_DOWN}"},
            ),
            save_screenshot={},
        )

        self.assertTrue(strategy._should_capture_post_action_screenshot(response))


if __name__ == "__main__":
    unittest.main()

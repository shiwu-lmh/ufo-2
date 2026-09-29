import unittest

from aip.messages import Result, ResultStatus
from ufo.agents.processors.schemas.target import TargetInfo, TargetKind
from ufo.agents.processors.context.host_agent_processing_context import (
    HostAgentProcessorContext,
)
from ufo.agents.processors.core.processor_framework import ProcessingContext
from ufo.agents.processors.schemas.response_schema import HostAgentResponse
from ufo.agents.processors.strategies.host_agent_processing_strategy import (
    HostActionExecutionStrategy,
)
from ufo.module.context import Context


class _RecordingDispatcher:
    def __init__(self):
        self.commands = []

    async def execute_commands(self, commands):
        self.commands.extend(commands)
        return [Result(status=ResultStatus.SUCCESS, result=None)]


class _FailingSelectionDispatcher(_RecordingDispatcher):
    async def execute_commands(self, commands):
        self.commands.extend(commands)
        return [
            Result(
                status=ResultStatus.FAILURE,
                error="Failed to set focus on window",
                result=None,
            )
        ]


class HostApplicationRoutingTests(unittest.TestCase):
    def test_wps_selection_launches_wps_before_assigning_app_agent(self):
        async def run():
            dispatcher = _RecordingDispatcher()
            local = HostAgentProcessorContext(
                request="打开 WPS 文字，点击新建"
            )
            local.target_registry.register(
                TargetInfo(
                    kind=TargetKind.WINDOW,
                    id="1",
                    name="ufo_test – action_step5.png",
                )
            )
            global_context = Context()
            global_context.attach_command_dispatcher(dispatcher)
            context = ProcessingContext(
                global_context=global_context, local_context=local
            )
            response = HostAgentResponse(
                observation="",
                thought="",
                status="ASSIGN",
                function="select_application_window",
                arguments={"id": "1", "name": "ufo_test – action_step5.png"},
            )
            context.set_local("parsed_response", response)
            context.set_local("function_name", response.function)

            result = await HostActionExecutionStrategy().execute(None, context)

            self.assertEqual(dispatcher.commands[0].tool_name, "run_shell")
            self.assertEqual(
                dispatcher.commands[0].parameters, {"bash_command": "wps"}
            )
            self.assertEqual(result.data["status"], "CONTINUE")
            self.assertTrue(result.data["clear_application_selection"])

        self._run_async(run())

    def test_wps_request_forces_launch_when_model_selected_screenshot_window(self):
        target = TargetInfo(
            kind=TargetKind.WINDOW,
            id="1",
            name="ufo_test – action_step5.png",
        )

        alias = HostActionExecutionStrategy.launch_alias_for_target(
            "打开 WPS 文字，点击新建", target
        )

        self.assertEqual(alias, "wps")

    def test_wps_request_does_not_relaunch_a_real_wps_window(self):
        target = TargetInfo(
            kind=TargetKind.WINDOW,
            id="1",
            name="UFO_visual_fallback_test.docx - WPS Office",
        )

        alias = HostActionExecutionStrategy.launch_alias_for_target(
            "打开 WPS 文字，点击新建", target
        )

        self.assertIsNone(alias)

    def test_failed_window_selection_does_not_assign_app_agent(self):
        async def run():
            dispatcher = _FailingSelectionDispatcher()
            local = HostAgentProcessorContext(request="打开 WPS 文字")
            local.target_registry.register(
                TargetInfo(kind=TargetKind.WINDOW, id="1", name="WPS Office")
            )
            global_context = Context()
            global_context.attach_command_dispatcher(dispatcher)
            context = ProcessingContext(
                global_context=global_context, local_context=local
            )
            response = HostAgentResponse(
                observation="",
                thought="",
                status="ASSIGN",
                function="select_application_window",
                arguments={"id": "1", "name": "WPS Office"},
            )
            context.set_local("parsed_response", response)
            context.set_local("function_name", response.function)

            result = await HostActionExecutionStrategy().execute(None, context)

            self.assertEqual(result.data["status"], "ERROR")
            self.assertIsNone(result.data["selected_target_id"])
            self.assertIsNone(result.data["target"])
            self.assertTrue(result.data["clear_application_selection"])

        self._run_async(run())

    def test_edge_request_forces_launch_when_model_selected_another_window(self):
        target = TargetInfo(kind=TargetKind.WINDOW, id="2", name="ChatGPT")

        alias = HostActionExecutionStrategy.launch_alias_for_target(
            "打开edge浏览器，访问百度", target
        )

        self.assertEqual(alias, "msedge")

    def test_edge_request_does_not_relaunch_edge_window(self):
        target = TargetInfo(kind=TargetKind.WINDOW, id="1", name="Microsoft Edge")

        alias = HostActionExecutionStrategy.launch_alias_for_target(
            "打开Edge浏览器，访问百度", target
        )

        self.assertIsNone(alias)

    def test_unrelated_request_does_not_force_edge_launch(self):
        target = TargetInfo(kind=TargetKind.WINDOW, id="2", name="ChatGPT")

        alias = HostActionExecutionStrategy.launch_alias_for_target(
            "打开网易云音乐", target
        )

        self.assertIsNone(alias)

    def test_forced_edge_launch_keeps_host_in_control_until_refresh(self):
        async def run():
            dispatcher = _RecordingDispatcher()
            local = HostAgentProcessorContext(
                request="打开edge浏览器，访问百度",
            )
            local.target_registry.register(
                TargetInfo(kind=TargetKind.WINDOW, id="2", name="ChatGPT")
            )
            global_context = Context()
            global_context.attach_command_dispatcher(dispatcher)
            context = ProcessingContext(
                global_context=global_context, local_context=local
            )
            response = HostAgentResponse(
                observation="",
                thought="",
                status="ASSIGN",
                function="select_application_window",
                arguments={"id": "2", "name": "ChatGPT"},
            )
            context.set_local("parsed_response", response)
            context.set_local("function_name", response.function)

            result = await HostActionExecutionStrategy().execute(None, context)

            self.assertEqual(result.data["status"], "CONTINUE")
            self.assertTrue(result.data["clear_application_selection"])
            self.assertEqual(dispatcher.commands[0].tool_name, "run_shell")
            self.assertEqual(
                dispatcher.commands[0].parameters, {"bash_command": "msedge"}
            )

        self._run_async(run())

    def _run_async(self, coroutine):
        import asyncio

        asyncio.run(coroutine)


if __name__ == "__main__":
    unittest.main()

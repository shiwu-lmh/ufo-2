import unittest
from types import SimpleNamespace

from aip.messages import Command
from ufo.client.computer import CommandRouter


class _FakeComputer:
    def __init__(self):
        self.selection_attempts = 0
        self.refresh_commands = []

    def command2tool(self, command):
        return SimpleNamespace(
            tool_name=command.tool_name,
            parameters=command.parameters,
            namespace="HostUIExecutor" if command.tool_type == "action" else "UIDataCollector",
        )

    async def run_actions(self, tool_calls):
        command = tool_calls[0]
        if command.tool_name == "select_application_window":
            self.selection_attempts += 1
            if self.selection_attempts == 1:
                return [
                    SimpleNamespace(
                        is_error=False,
                        data="Error: focus failed",
                        content=[],
                        namespace="HostUIExecutor",
                    )
                ]
            return [
                SimpleNamespace(
                    is_error=False,
                    data={"root_name": "WPS"},
                    content=[],
                    namespace="HostUIExecutor",
                )
            ]

        if command.tool_name == "get_desktop_app_info":
            self.refresh_commands.append(command.tool_name)
            return [
                SimpleNamespace(
                    is_error=False,
                    data=[{"id": "9", "name": "WPS Office"}],
                    content=[],
                    namespace="UIDataCollector",
                )
            ]

        raise AssertionError(f"Unexpected tool: {command.tool_name}")


class _CoordinateRetryComputer:
    def __init__(self):
        self.coordinate_attempts = 0
        self.screenshot_attempts = 0
        self.refresh_commands = []

    def command2tool(self, command):
        return SimpleNamespace(
            tool_name=command.tool_name,
            parameters=command.parameters,
            namespace="AppUIExecutor" if command.tool_type == "action" else "UIDataCollector",
        )

    async def run_actions(self, tool_calls):
        command = tool_calls[0]
        if command.tool_name == "capture_window_screenshot":
            self.screenshot_attempts += 1
            self.refresh_commands.append(command.tool_name)
            image = "same" if self.screenshot_attempts < 5 else "changed"
            return [
                SimpleNamespace(
                    is_error=False,
                    data=f"data:image/png;base64,{image}",
                    content=[],
                    namespace="UIDataCollector",
                )
            ]

        if command.tool_name == "click_on_coordinates":
            self.coordinate_attempts += 1
            return [
                SimpleNamespace(
                    is_error=False,
                    data="Click action has been executed",
                    content=[],
                    namespace="AppUIExecutor",
                )
            ]

        raise AssertionError(f"Unexpected tool: {command.tool_name}")


class _FakeComputerManager:
    def __init__(self, computer):
        self.computer = computer

    async def get_or_create(self, **_kwargs):
        return self.computer


class WindowSelectionRetryTests(unittest.IsolatedAsyncioTestCase):
    async def test_window_selection_refreshes_and_retries_after_focus_failure(self):
        computer = _FakeComputer()
        router = CommandRouter(_FakeComputerManager(computer), action_retries=2)

        results = await router.execute(
            agent_name="HostAgent",
            process_name=None,
            root_name=None,
            commands=[
                Command(
                    tool_name="select_application_window",
                    parameters={"id": "1", "name": "WPS Office"},
                    tool_type="action",
                )
            ],
        )

        self.assertEqual(computer.selection_attempts, 2)
        self.assertEqual(computer.refresh_commands, ["get_desktop_app_info"])
        self.assertEqual(results[0].status.value, "success")

    async def test_coordinate_click_retries_and_checks_screenshot_state(self):
        computer = _CoordinateRetryComputer()
        router = CommandRouter(_FakeComputerManager(computer), action_retries=2)

        results = await router.execute(
            agent_name="AppAgent",
            process_name="test",
            root_name="TEST.EXE",
            commands=[
                Command(
                    tool_name="click_on_coordinates",
                    parameters={"x": 0.5, "y": 0.5},
                    tool_type="action",
                )
            ],
        )

        self.assertEqual(computer.coordinate_attempts, 2)
        self.assertEqual(computer.screenshot_attempts, 5)
        self.assertEqual(results[0].status.value, "success")


if __name__ == "__main__":
    unittest.main()

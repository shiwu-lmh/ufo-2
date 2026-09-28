import asyncio
import concurrent.futures
import copy
import inspect
import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional

from fastmcp import Client, FastMCP
from fastmcp.client.client import CallToolResult
from mcp.types import TextContent

from ufo.client.mcp.mcp_server_manager import BaseMCPServer, MCPServerManager
from ufo.client.action_retry import execute_with_retries
from ufo.client.visual_fallback import screenshot_changed
from aip.messages import Command, Result, MCPToolCall, ResultStatus
import ufo.client.mcp.local_servers

# Load all local MCP servers
ufo.client.mcp.local_servers.load_all_servers()


class Computer:
    """
    Basic class for managing computer operations and actions.
    """

    _data_collection_namespaces: str = "data_collection"
    _action_namespaces: str = "action"

    def __init__(
        self,
        name: str,
        process_name: str,
        mcp_server_manager: MCPServerManager,
        data_collection_servers_config: Optional[List[Dict[str, Any]]] = None,
        action_servers_config: Optional[List[Dict[str, Any]]] = None,
    ):
        """
        Initialize the computer with a name and optional agent name.
        :param name: The name of the computer.
        :param data_collection_servers_config: Configuration for data collection servers.
        :param action_servers_config: Configuration for action servers.
        """

        self._name = name
        self._process_name = process_name

        self.data_collection_servers_config = data_collection_servers_config
        self.action_servers_config = action_servers_config

        self._data_collection_servers = {}
        self._action_servers = {}

        self._tools_registry: Dict[str, MCPToolCall] = {}

        self.mcp_server_manager = mcp_server_manager

        # Automatically register meta tools for the computer.

        self._meta_tools: Dict[str, Callable] = {}

        self.logger = logging.getLogger(self.__class__.__name__)

        # Thread pool executor for isolating blocking MCP tool calls
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=10, thread_name_prefix="mcp_tool_"
        )

        # Tool execution timeout (seconds)
        self._tool_timeout = 6000  # 5 minutes

        # Register meta tools
        for attr in dir(self):
            method = getattr(self, attr)
            if callable(method) and hasattr(method, "_meta_tool_name"):
                name = getattr(method, "_meta_tool_name")
                self._meta_tools[name] = method

    async def async_init(self) -> None:
        """
        Asynchronous initialization of the computer.
        """
        self._data_collection_servers = self._init_data_collection_servers()
        self._action_servers = self._init_action_servers()

        # Register MCP servers in parallel
        await asyncio.gather(
            self.register_mcp_servers(
                self._data_collection_servers,
                tool_type=self._data_collection_namespaces,
            ),
            self.register_mcp_servers(
                self._action_servers, tool_type=self._action_namespaces
            ),
        )

    @staticmethod
    def meta_tool(name: str):
        """
        Decorator to register a function as a meta tool.
        :param name: The name of the meta tool.
        :return: A decorator that registers the function as a meta tool.
        """

        def decorator(func):
            func._meta_tool_name = name  # Store the meta tool name
            return func

        return decorator

    def _init_data_collection_servers(self) -> Dict[str, BaseMCPServer]:
        """
        Initialize data collection servers for the computer of the
        """
        # Get the base directory for UFO2
        for data_collection_server in self.data_collection_servers_config:

            # If the server is set to auto-start, create a FastMCP server
            namespace = data_collection_server.get("namespace")
            reset = data_collection_server.get("reset", False)

            if not namespace:
                namespace = "default_data_collection"

            mcp_server = self.mcp_server_manager.create_or_get_server(
                mcp_config=data_collection_server,
                reset=reset,
                process_name=self._process_name,
            )

            self._data_collection_servers[namespace] = mcp_server

        return self._data_collection_servers

    def _init_action_servers(self) -> Dict[str, BaseMCPServer]:
        """
        Initialize action servers for the computer.
        """
        # Get the base directory for UFO2
        for action_server in self.action_servers_config:
            # If the server is set to auto-start, create a FastMCP server
            namespace = action_server.get("namespace")
            reset = action_server.get("reset", False)

            if not namespace:
                namespace = "default_action"

            mcp_server = self.mcp_server_manager.create_or_get_server(
                mcp_config=action_server, reset=reset, process_name=self._process_name
            )

            self._action_servers[namespace] = mcp_server

        return self._action_servers

    async def _run_action(self, tool_call: MCPToolCall) -> CallToolResult:
        """
        Run a one-step action on the computer.
        :param tool_call: The tool call to run.
        :return: The result of the single action.
        """

        tool_key = tool_call.tool_key
        tool_info = self._tools_registry.get(tool_key, None)
        namespace = tool_info.namespace if tool_info else None

        self.logger.debug(
            f"Running [{namespace}] tool: {tool_info.tool_name} with parameters: {tool_info.parameters}"
        )

        if not tool_info:
            raise ValueError(f"Tool {tool_key} is not registered.")

        # Check if the tool is a meta tool for listing tools
        if tool_info.tool_name in self._meta_tools:
            # Special case for listing tools, which does not require a server call

            parameters = tool_info.parameters or {}
            self.logger.info(
                f"Running meta tool: {tool_info.tool_name} with parameters: {parameters}"
            )

            result = self._meta_tools[tool_info.tool_name](**parameters)

            # If the result is an awaitable, await it
            if inspect.isawaitable(result):
                return await result
            else:
                return result

        server = tool_info.mcp_server.server

        tool_name = tool_info.tool_name
        params = tool_info.parameters or {}

        # Run MCP tool call in a separate thread to avoid blocking the event loop
        # This prevents blocking operations (like time.sleep) in MCP tools from
        # affecting the main event loop and causing WebSocket disconnections
        def _call_tool_in_thread():
            """
            Execute MCP tool call in an isolated thread with its own event loop.
            This prevents blocking operations in MCP tools from blocking the main event loop.
            """
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:

                async def _do_call():
                    async with Client(server) as client:
                        return await client.call_tool(
                            name=tool_name, arguments=params, raise_on_error=False
                        )

                return loop.run_until_complete(_do_call())
            finally:
                loop.close()

        try:
            # Execute in thread pool with timeout protection
            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(self._executor, _call_tool_in_thread),
                timeout=self._tool_timeout,
            )

            self.logger.debug(f"Tool {tool_name} executed successfully")
            return result

        except asyncio.TimeoutError:
            # Tool execution timeout
            error_msg = (
                f"Tool {tool_name} execution timed out after {self._tool_timeout}s"
            )
            self.logger.error(error_msg)

            # Return timeout error result
            error_content = [
                TextContent(
                    type="text",
                    text=error_msg,
                    annotations=None,
                    meta=None,
                )
            ]
            return CallToolResult(
                data=None, content=error_content, structured_content=None, is_error=True
            )
        except Exception as e:
            # Other exceptions
            error_msg = f"Tool {tool_name} execution failed: {str(e)}"
            self.logger.error(error_msg, exc_info=True)

            error_content = [
                TextContent(
                    type="text",
                    text=error_msg,
                    annotations=None,
                    meta=None,
                )
            ]
            return CallToolResult(
                data=None, content=error_content, structured_content=None, is_error=True
            )

    async def run_actions(self, tool_calls: List[MCPToolCall]) -> List[CallToolResult]:
        """
        Run an action on the computer.
        :param tool_calls: The list of tool calls to run.
        :return: The result of the action.
        """

        results = []
        for tool_call in tool_calls:
            result = await self._run_action(tool_call)
            results.append(result)
            self.logger.debug(
                f"Action {tool_call.tool_name} executed with result: {result}"
            )

        return results

    async def register_mcp_servers(
        self, server_dict: Dict[str, BaseMCPServer], tool_type: str
    ) -> None:
        """
        Register a tool with the computer.
        :param server_dict: A dictionary mapping namespaces to MCP servers.
        :param tool_type: The type of the tool (e.g., "action", "data_collection").
        :return: None
        """
        tasks = [
            self.register_one_mcp_server(namespace, tool_type, server)
            for namespace, server in server_dict.items()
        ]

        # Run all registration tasks concurrently
        await asyncio.gather(*tasks)

    async def register_one_mcp_server(
        self, namespace: str, tool_type: str, mcp_server: BaseMCPServer
    ) -> None:
        """
        Register tools from a single MCP server.
        :param namespace: The namespace of the tools.
        :param tool_type: The type of the tools (e.g., "action", "data_collection").
        :param server: The MCP server to register tools from.
        :return: None
        """

        self.logger.info(
            f"Registering tools from [{namespace}] server for ({tool_type})."
        )

        async with Client(mcp_server.server) as client:
            tools = await client.list_tools()

            for tool in tools:
                tool_key = self.make_tool_key(tool_type, tool.name)
                if tool_key not in self._tools_registry:
                    self._register_tool(
                        tool_key=tool_key,
                        tool_name=tool.name,
                        title=tool.title,
                        namespace=namespace,
                        tool_type=tool_type,
                        description=tool.description,
                        input_schema=(
                            tool.inputSchema
                            if hasattr(tool, "inputSchema") and tool.inputSchema
                            else {}
                        ),
                        output_schema=(
                            tool.outputSchema
                            if hasattr(tool, "outputSchema") and tool.outputSchema
                            else {}
                        ),
                        mcp_server=mcp_server,
                        meta=(tool.meta),
                        annotations=(
                            tool.annotations.model_dump() if tool.annotations else None
                        ),
                    )
                else:
                    self.logger.warning(
                        f"Tool {tool_key} is already registered. Skipping registration."
                    )

            for meta_tool_name, meta_tool_func in self._meta_tools.items():
                tool_key = self.make_tool_key(tool_type, meta_tool_name)

                if tool_key not in self._tools_registry:
                    # Register the meta tool with the computer
                    self.logger.info(
                        f"Registering meta tool: {meta_tool_name} with key: {tool_key} for computer {self._name} for MCP server {namespace}."
                    )
                    self._register_tool(
                        tool_key=tool_key,
                        tool_name=meta_tool_name,
                        title=meta_tool_func.__name__,
                        namespace=namespace,
                        tool_type=tool_type,
                        description=meta_tool_func.__doc__ or "Meta tool",
                        input_schema=meta_tool_func.__annotations__,
                        output_schema=meta_tool_func.__annotations__,
                        mcp_server=mcp_server,
                    )

    def _register_tool(
        self,
        tool_key: str,
        tool_name: str,
        title: str,
        namespace: str,
        tool_type: str,
        description: str,
        input_schema: Optional[Dict[str, Any]],
        output_schema: Optional[Dict[str, Any]],
        mcp_server: BaseMCPServer,
        meta: Optional[Dict[str, Any]] = None,
        annotations: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Register a tool with the computer in its tools registry.
        :param tool_key: Unique key for the tool, e.g., "tool_type.tool_name".
        :param tool_name: The name of the tool.
        :param title: The title of the tool, used for display.
        :param namespace: The namespace of the tool.
        :param tool_type: The type of the tool (e.g., "action", "
        :param description: The description of the tool.
        :param input_schema: Optional input schema for the tool.
        :param output_schema: Optional output schema for the tool.
        :param mcp_server: The MCP server where the tool is registered.
        """
        if tool_key in self._tools_registry:
            raise ValueError(f"Tool {tool_key} is already registered.")

        tool_info = MCPToolCall(
            tool_key=tool_key,
            tool_name=tool_name,
            title=title,
            description=description,
            namespace=namespace,
            tool_type=tool_type,
            input_schema=input_schema,
            output_schema=output_schema,
            mcp_server=mcp_server,
            meta=meta,
            annotations=annotations,
        )
        self._tools_registry[tool_key] = tool_info

    async def add_server(
        self,
        namespace: str,
        mcp_server: BaseMCPServer,
        tool_type: Optional[str] = None,
    ) -> None:
        """
        Add a server and its tools to the computer.
        :param namespace: The namespace of the server.
        :param server: The MCP server to add.
        :param tool_type: Optional type of tools (e.g., "action", "data_collection").
        :return: None
        """
        if tool_type is None:
            raise ValueError(
                f"Tool type must be specified (i.e., {self._data_collection_namespaces} or {self._action_namespaces})."
            )

        if tool_type == self._data_collection_namespaces:
            self._data_collection_servers[namespace] = mcp_server
        elif tool_type == self._action_namespaces:
            self._action_servers[namespace] = mcp_server
        else:
            raise ValueError(
                f"Invalid tool type: {tool_type}. Must be one of {self._data_collection_namespaces} or {self._action_namespaces}."
            )

        await self.register_one_mcp_server(namespace, tool_type, mcp_server)

    async def delete_server(
        self, namespace: str, tool_type: Optional[str] = None
    ) -> None:
        """
        Delete a server and its tools from the computer.
        :param namesspace: The namespace of the server to delete.
        :param tool_type: Optional type of tools to delete (e.g., "action", "data_collection").
        :return: None
        """
        keys_to_remove = [
            key
            for key, tool in self._tools_registry.items()
            if tool.namespace == namespace
            and (tool_type is None or tool.tool_type == tool_type)
        ]

        for key in keys_to_remove:
            del self._tools_registry[key]

        # Remove the server from the action or data collection servers
        if tool_type == self._data_collection_namespaces:
            self._data_collection_servers.pop(namespace, None)
        elif tool_type == self._action_namespaces:
            self._action_servers.pop(namespace, None)

    @meta_tool("list_tools")
    async def list_tools(
        self,
        tool_type: Optional[str] = None,
        namespace: Optional[str] = None,
        remove_meta: bool = True,
    ) -> CallToolResult:
        """
        Get the available tools of a specific type (action or data_collection).
        :param tool_type: The type of tools to retrieve (e.g., "action", "data_collection").
        :param namespace: Optional namespace to filter tools.
        :param remove_meta: Whether to remove meta tools from the list for listing.
        :return: A list of MCPToolCall objects representing the available tools.
        """

        tools = []

        for tool in self._tools_registry.values():
            if (
                # Check if the tool matches the specified type and namespace
                (tool_type is None or tool.tool_type == tool_type)
                # Check if the tool matches the specified namespace
                and (namespace is None or tool.namespace == namespace)
                # Check if the tool is not a meta tool or if meta tools should be included
                and (not remove_meta or tool.tool_name not in self._meta_tools)
            ):
                tools.append(tool.tool_info.model_dump())

        content = [
            TextContent(
                type="text",
                text=json.dumps(tools),
                annotations=None,
                meta=None,
            )
        ]

        tool_result = CallToolResult(
            data=tools,
            content=content,
            structured_content=None,
        )

        return tool_result

    def command2tool(self, command: Command) -> MCPToolCall:
        """
        Convert a Command object to an MCPToolCall object.
        :param command: The Command object to convert.
        :return: An MCPToolCall object representing the tool call.
        """
        tool_name = command.tool_name
        tool_type = command.tool_type

        if not tool_type:
            if (
                self.make_tool_key(self._data_collection_namespaces, tool_name)
                in self._tools_registry
            ):
                tool_type = self._data_collection_namespaces
                Warning(
                    f"Tool {tool_name} is registered as a data collection tool, but no tool type was specified in the command. Using {tool_type} as default."
                )

            elif (
                self.make_tool_key(self._action_namespaces, tool_name)
                in self._tools_registry
            ):
                tool_type = self._action_namespaces

                Warning(
                    f"Tool {tool_name} is registered as an action tool, but no tool type was specified in the command. Using {tool_type} as default."
                )
            else:
                raise ValueError(
                    f"Tool {tool_name} is not registered in the computer's tools registry with {self._data_collection_namespaces} or {self._action_namespaces} as tool type."
                )

        tool_key = self.make_tool_key(tool_type, tool_name)
        tool_info = self._tools_registry.get(tool_key, None)

        if not tool_info:
            raise ValueError(
                f"Tool {tool_key} is not registered in current computer: {self._name}"
            )

        parameters = copy.deepcopy(command.parameters) if command.parameters else {}

        tool_info.parameters = parameters

        if not tool_info:
            raise ValueError(f"Tool {tool_key} is not registered.")
        return tool_info

    @staticmethod
    def make_tool_key(tool_type: str, tool_name: str) -> str:
        """
        Create a unique key for a tool based on its type and name.
        :param tool_type: The type of the tool (e.g., "action", "data_collection").
        :param tool_name: The name of the tool.
        :return: A unique key for the tool in the format "tool_type::tool_name".
        """
        return f"{tool_type}::{tool_name}"

    @property
    def data_collection_servers(self) -> Dict[str, FastMCP]:
        """
        Get the data collection servers for the computer.
        """

        return self._data_collection_servers

    @property
    def action_servers(self) -> Dict[str, FastMCP]:
        """
        Get the action servers for the computer.
        """

        return self._action_servers

    @property
    def name(self) -> str:
        """
        Get the name of the computer
        """
        return self._name


class ComputerManager:
    """Manager for managing multiple Computer instances.
    This class provides methods to get or create Computer instances based on configurations.
    """

    _configs_key = "mcp"

    def __init__(self, configs: Dict[str, Any], mcp_server_manager: MCPServerManager):
        """
        Initialize the ComputerManager with configurations.
        :param configs: Configuration dictionary containing agent_name, process_name, and root_name.
        """
        self.configs = configs
        self.mcp_server_manager = mcp_server_manager
        self.computers = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    async def get_or_create(
        self,
        agent_name: str,
        process_name: Optional[str] = None,
        root_name: Optional[str] = None,
    ) -> Computer:
        """
        Get or create a Computer instance based on the provided configuration.
        :param config: Configuration dictionary containing agent_name, process_name, and root_name.
        :return: An instance of Computer.
        """

        key = f"{agent_name}::{process_name}::{root_name or 'default'}"

        if key not in self.computers:

            # Get the configuration for the agent
            mcp_config = self.configs.get(self._configs_key, {})
            agent_config = mcp_config.get(agent_name, {})
            if not agent_config:
                raise ValueError(f"Agent configuration for {agent_name} not found.")

            if root_name not in agent_config:
                self.logger.info(
                    f"Root name '{root_name}' not found in agent configuration for {agent_name}. Using default configuration."
                )
                root = "default"
            else:
                root = root_name

            agent_instance_config = agent_config.get(root, None)

            if agent_instance_config is None:
                raise ValueError(
                    f"Agent configuration for root_name={root} not found for agent_name={agent_name}."
                )

            data_collection_servers_config = agent_instance_config.get(
                Computer._data_collection_namespaces, []
            )
            action_servers_config = agent_instance_config.get(
                Computer._action_namespaces, []
            )

            computer = Computer(
                name=key,
                process_name=process_name,
                data_collection_servers_config=data_collection_servers_config,
                action_servers_config=action_servers_config,
                mcp_server_manager=self.mcp_server_manager,
            )
            await computer.async_init()

            self.logger.info(f"Initialized computer: {key}")

            self.computers[key] = computer

        return self.computers[key]

    def reset(self) -> None:
        """
        Reset the ComputerManager by clearing all Computer instances.
        This is useful for reinitializing the manager without restarting the application.
        """
        self.computers.clear()


class CommandRouter:
    """
    Router for executing commands on a Computer instance.
    This class takes a ComputerManager and executes commands on the appropriate Computer instance.
    """

    def __init__(
        self,
        computer_manager: ComputerManager,
        action_retries: Optional[int] = None,
    ):
        """
        Initialize the CommandRouter with a ComputerManager.
        :param manager: An instance of ComputerManager to manage Computer instances.
        """
        self.computer_manager = computer_manager
        self.logger = logging.getLogger(self.__class__.__name__)
        if action_retries is None:
            try:
                from config.config_loader import get_ufo_config

                action_retries = get_ufo_config().system.get("action_retry", 2)
            except Exception:
                action_retries = 2
        self.action_retries = max(0, int(action_retries))
        try:
            from config.config_loader import get_ufo_config

            self.visual_fallback_enabled = bool(
                get_ufo_config().system.get("mcp_fallback_to_ui", True)
            )
        except Exception:
            self.visual_fallback_enabled = True

    _UI_ACTIONS_THAT_USE_CONTROLS = frozenset(
        {
            "click_input",
            "set_edit_text",
            "keyboard_input",
            "wheel_mouse_input",
            "texts",
        }
    )
    _COORDINATE_ACTIONS = frozenset({"click_on_coordinates"})
    _WINDOW_ACTIONS = frozenset({"select_application_window"})

    async def _refresh_ui_before_retry(
        self, computer: Computer, command: Command
    ) -> None:
        """Refresh the screenshot and UIA control map before retrying an action."""
        if command.tool_type != "action":
            return

        if command.tool_name in self._WINDOW_ACTIONS:
            refresh_commands = [
                Command(
                    tool_name="get_desktop_app_info",
                    parameters={"remove_empty": True, "refresh_app_windows": True},
                    tool_type="data_collection",
                )
            ]
        elif command.tool_name in self._UI_ACTIONS_THAT_USE_CONTROLS:
            refresh_commands = [
                Command(
                    tool_name="capture_window_screenshot",
                    parameters={},
                    tool_type="data_collection",
                ),
                Command(
                    tool_name="get_app_window_controls_target_info",
                    parameters={
                        "field_list": [
                            "control_text",
                            "control_type",
                            "control_rect",
                            "is_enabled",
                            "is_visible",
                        ]
                    },
                    tool_type="data_collection",
                ),
            ]
        elif command.tool_name in self._COORDINATE_ACTIONS:
            refresh_commands = [
                Command(
                    tool_name="capture_window_screenshot",
                    parameters={},
                    tool_type="data_collection",
                )
            ]
        else:
            return

        for refresh_command in refresh_commands:
            try:
                refresh_tool = computer.command2tool(refresh_command)
                refresh_results = await computer.run_actions([refresh_tool])
                if (
                    refresh_command.tool_name
                    in {"get_app_window_controls_target_info", "get_desktop_app_info"}
                    and self._is_successful_action_result(refresh_results)
                ):
                    self._refresh_command_target(command, refresh_results[0].data)
            except Exception as exc:
                self.logger.warning(
                    "UI refresh before action retry failed for %s: %s",
                    refresh_command.tool_name,
                    exc,
                )

    @staticmethod
    def _refresh_command_target(command: Command, controls: Any) -> None:
        """Rebind a control action to the refreshed ID with the same exact name."""
        if not isinstance(controls, list) or not command.parameters:
            return

        target_name = command.parameters.get("name")
        if not target_name:
            return

        for control in controls:
            if isinstance(control, dict):
                control_id = control.get("id")
                control_name = control.get("name")
            else:
                control_id = getattr(control, "id", None)
                control_name = getattr(control, "name", None)
            if control_id is not None and control_name == target_name:
                command.parameters["id"] = str(control_id)
                return

    @staticmethod
    def _is_successful_action_result(call_results: Any) -> bool:
        """Treat MCP warnings about a mismatched control as action failures."""
        if not call_results:
            return False

        call_result = call_results[0]
        if getattr(call_result, "is_error", False):
            return False

        messages = []
        data = getattr(call_result, "data", None)
        if isinstance(data, str):
            messages.append(data)
        for content in getattr(call_result, "content", None) or []:
            text = getattr(content, "text", None)
            if isinstance(text, str):
                messages.append(text)

        failure_prefixes = ("warning:", "error:", "an error occurred")
        return not any(
            message.strip().lower().startswith(failure_prefixes)
            for message in messages
        )

    @staticmethod
    def _action_result_error(call_result: CallToolResult) -> str:
        """Extract a useful error or warning message from an MCP result."""
        data = getattr(call_result, "data", None)
        if isinstance(data, str) and data.strip():
            return data
        for content in getattr(call_result, "content", None) or []:
            text = getattr(content, "text", None)
            if isinstance(text, str) and text.strip():
                return text
        return "MCP action failed"

    async def _capture_window_screenshot(self, computer: Computer) -> Optional[str]:
        """Capture a fresh app screenshot for action postcondition checking."""
        try:
            screenshot_command = Command(
                tool_name="capture_window_screenshot",
                parameters={},
                tool_type="data_collection",
            )
            screenshot_tool = computer.command2tool(screenshot_command)
            screenshot_results = await computer.run_actions([screenshot_tool])
            if not screenshot_results or screenshot_results[0].is_error:
                return None
            screenshot = screenshot_results[0].data
            return screenshot if isinstance(screenshot, str) else None
        except Exception as exc:
            self.logger.debug("Screenshot capture for postcondition failed: %s", exc)
            return None

    async def _locate_visual_candidate(
        self, computer: Computer, target_name: str
    ) -> Optional[Dict[str, Any]]:
        """Ask the UI collector to locate a target in a newly captured screenshot."""
        locate_command = Command(
            tool_name="locate_control_visually",
            parameters={"name": target_name},
            tool_type="data_collection",
        )
        locate_tool = computer.command2tool(locate_command)
        locate_results = await computer.run_actions([locate_tool])
        if not locate_results or locate_results[0].is_error:
            return None

        candidates = locate_results[0].data
        if isinstance(candidates, dict):
            candidates = candidates.get("candidates", [])
        if not isinstance(candidates, list):
            return None

        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            try:
                x = float(candidate["x"])
                y = float(candidate["y"])
            except (KeyError, TypeError, ValueError):
                continue
            if 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0:
                return {"x": x, "y": y, "score": candidate.get("score")}
        return None

    async def _execute_visual_fallback(
        self, computer: Computer, command: Command, call_id: Optional[str]
    ) -> tuple[list[CallToolResult], Optional[MCPToolCall], Optional[Exception]]:
        """Locate a failed UIA click visually and click it with PyAutoGUI."""
        if not self.visual_fallback_enabled:
            return [], None, RuntimeError("Visual UI fallback is disabled")

        target_name = str((command.parameters or {}).get("name") or "").strip()
        if not target_name:
            return [], None, RuntimeError(
                "Visual UI fallback requires the original control name"
            )

        async def _run_visual_click():
            before = await self._capture_window_screenshot(computer)
            candidate = await self._locate_visual_candidate(computer, target_name)
            if not candidate:
                return [], None, RuntimeError(
                    f"Visual locator did not find control: {target_name}. "
                    "Do not repeat the same click_input target; inspect the fresh "
                    "screenshot and use click_on_coordinates if the target is visible."
                )

            click_command = Command(
                tool_name="click_on_coordinates",
                parameters={
                    "x": candidate["x"],
                    "y": candidate["y"],
                    "button": (command.parameters or {}).get("button", "left"),
                    "double": bool((command.parameters or {}).get("double", False)),
                },
                tool_type="action",
                call_id=call_id,
            )
            click_tool = computer.command2tool(click_command)
            click_results = await computer.run_actions([click_tool])
            if not click_results or click_results[0].is_error:
                return click_results, click_tool, RuntimeError(
                    "PyAutoGUI coordinate click failed"
                )

            after = await self._capture_window_screenshot(computer)
            changed = screenshot_changed(before, after)
            if changed is False:
                return [], click_tool, RuntimeError(
                    "Visual coordinate click completed but the screenshot was unchanged"
                )
            return click_results, click_tool, None

        def _visual_succeeded(outcome) -> bool:
            call_results, _tool_call, execution_error = outcome
            return (
                execution_error is None
                and self._is_successful_action_result(call_results)
            )

        async def _refresh_visual_retry(retry_number: int) -> None:
            self.logger.warning(
                "Visual fallback for %s failed on retry %d/%d; refreshing UI state",
                target_name,
                retry_number,
                self.action_retries,
            )
            await self._refresh_ui_before_retry(computer, command)

        return await execute_with_retries(
            _run_visual_click,
            max_retries=self.action_retries,
            is_success=_visual_succeeded,
            before_retry=_refresh_visual_retry if self.action_retries else None,
        )

    async def execute(
        self,
        agent_name: str,
        process_name: Optional[str],
        root_name: Optional[str],
        commands: List[Command],
        early_exit: bool = True,
    ) -> List[Result]:
        """
        Execute a command on the appropriate Computer instance based on the provided configuration.
        :param agent_name: The name of the agent to execute the command for.
        :param process_name: The name of the process to control, or None if not specified
        :param root_name: The root name of the computer, or None if not specified.
        :param commands: The list of Command objects to execute.
        :param early_exit: If True, stop executing commands after the first failure.
        :return: The list of results from executing the commands.
        """

        computer = await self.computer_manager.get_or_create(
            agent_name=agent_name, process_name=process_name, root_name=root_name
        )

        results: List[Result] = []
        has_failed = False  # track if any command failed

        for command in commands:
            call_id = command.call_id

            # Handle commands without tool_name
            if not command.tool_name:
                results.append(
                    Result(
                        status=ResultStatus.SUCCESS,
                        result="No action taken.",
                        error="",
                        call_id=call_id,
                    )
                )
                continue

            # If there was a failure before and early_exit is enabled, skip subsequent commands
            if early_exit and has_failed:
                self.logger.warning(
                    f"Skipping command {call_id} (tool: {command.tool_name}) due to previous failure."
                )
                results.append(
                    Result(
                        status=ResultStatus.SKIPPED,
                        result=None,
                        error="Skipped due to previous failure (early_exit=True).",
                        call_id=call_id,
                        namespace=None,
                    )
                )
                continue  # Skip this iteration, do not execute command

            max_attempts = (
                1 + self.action_retries
                if command.tool_type == "action"
                and command.tool_name
                in self._UI_ACTIONS_THAT_USE_CONTROLS.union(
                    self._COORDINATE_ACTIONS, self._WINDOW_ACTIONS
                )
                else 1
            )
            verify_click_state = (
                command.tool_type == "action"
                and command.tool_name
                in {"click_input", *self._COORDINATE_ACTIONS}
            )
            async def _run_action():
                before_screenshot = (
                    await self._capture_window_screenshot(computer)
                    if verify_click_state
                    else None
                )
                try:
                    tool_call = computer.command2tool(command)
                    call_results = await computer.run_actions([tool_call])
                    execution_error = None
                except Exception as exc:
                    return [], None, exc

                if verify_click_state and self._is_successful_action_result(
                    call_results
                ):
                    after_screenshot = await self._capture_window_screenshot(computer)
                    if screenshot_changed(before_screenshot, after_screenshot) is False:
                        self.logger.warning(
                            "%s action returned success but the screenshot did not change",
                            command.tool_name,
                        )
                        execution_error = RuntimeError(
                            f"{command.tool_name} completed but produced no visible state change"
                        )

                return call_results, tool_call, execution_error

            def _action_succeeded(outcome) -> bool:
                call_results, _tool_call, execution_error = outcome
                return (
                    execution_error is None
                    and self._is_successful_action_result(call_results)
                )

            async def _refresh_for_retry(retry_number: int) -> None:
                self.logger.warning(
                    "Command %s (tool: %s) failed on retry %d/%d; "
                    "refreshing UI state before the next attempt",
                    call_id,
                    command.tool_name,
                    retry_number,
                    max_attempts - 1,
                )
                await self._refresh_ui_before_retry(computer, command)

            call_results, tool_call, execution_error = await execute_with_retries(
                _run_action,
                max_retries=max_attempts - 1,
                is_success=_action_succeeded,
                before_retry=_refresh_for_retry if max_attempts > 1 else None,
            )

            ui_action_failed = not _action_succeeded(
                (call_results, tool_call, execution_error)
            )
            if (
                ui_action_failed
                and command.tool_type == "action"
                and command.tool_name in self._UI_ACTIONS_THAT_USE_CONTROLS
                and command.tool_name == "click_input"
            ):
                self.logger.warning(
                    "UIA action %s failed or produced no visible state change; "
                    "entering automatic visual fallback",
                    call_id,
                )
                fallback_outcome = await self._execute_visual_fallback(
                    computer, command, call_id
                )
                if _action_succeeded(fallback_outcome):
                    call_results, tool_call, execution_error = fallback_outcome
                else:
                    # Keep the visual fallback error when it ran, because it is
                    # the final action path and is more useful to the caller.
                    call_results, tool_call, execution_error = fallback_outcome

            namespace = tool_call.namespace if tool_call else None

            if execution_error is not None:
                final_result = Result(
                    status=ResultStatus.FAILURE,
                    error=str(execution_error),
                    result=None,
                    call_id=call_id,
                    namespace=namespace,
                )
            elif not call_results:
                final_result = Result(
                    status=ResultStatus.FAILURE,
                    error="MCP action returned no result",
                    result=None,
                    call_id=call_id,
                    namespace=namespace,
                )
            else:
                call_tool_result: CallToolResult = call_results[0]
                text_content = (
                    call_tool_result.data if call_tool_result.data else None
                )
                if self._is_successful_action_result(call_results):
                    final_result = Result(
                        status=ResultStatus.SUCCESS,
                        result=text_content,
                        error=None,
                        call_id=call_id,
                        namespace=namespace,
                    )
                else:
                    final_result = Result(
                        status=ResultStatus.FAILURE,
                        error=self._action_result_error(call_tool_result),
                        result=None,
                        call_id=call_id,
                        namespace=namespace,
                    )

            results.append(final_result)
            if final_result.status == ResultStatus.FAILURE:
                has_failed = True
                self.logger.warning(
                    "Command %s (tool: %s) failed after %d attempt(s): %s",
                    call_id,
                    command.tool_name,
                    max_attempts,
                    final_result.error,
                )

            # Sleep to avoid overwhelming the server with requests
            await asyncio.sleep(0.1)

        return results


def test_command_router():
    """
    Test function for the CommandRouter.
    This function creates a ComputerManager and a CommandRouter, then executes a sample command.
    """
    from config.config_loader import get_ufo_config

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    ufo_config = get_ufo_config()

    mcp_server_manager = MCPServerManager()
    computer_manager = ComputerManager(ufo_config.to_dict(), mcp_server_manager)
    command_router = CommandRouter(computer_manager)

    print("Starting CommandRouter test...")

    # Example command execution, all from the server
    commands = [
        Command(
            tool_name="get_desktop_app_info",
            tool_type="data_collection",
            parameters={"remove_empty": True, "refresh_app_windows": True},
        ),
        Command(
            tool_name="select_application_window",
            tool_type="action",
            parameters={"id": "2"},
        ),
    ]

    results1 = asyncio.run(
        command_router.execute(
            agent_name="HostAgent",  # From server
            process_name="",  # From server
            root_name="",  # From server
            commands=commands,
        )
    )

    commands = [
        # Command(
        #     tool_name="list_tools",
        #     parameters={"tool_type": "action"},
        #     tool_type="data_collection",
        # ),
        Command(
            tool_name="table2markdown",
            parameters={"sheet_name": "Sheet1"},
            tool_type="action",
        ),
    ]

    print(results1)

    results2 = asyncio.run(
        command_router.execute(
            agent_name="AppAgent",  # From server
            process_name="schedule",  # From server
            root_name="EXCEL.EXE",  # From server
            commands=commands,
        )
    )
    tool_list = results2[0].result
    print(results1)
    print(tool_list)

    # for tool in tool_list:
    #     print(tool.get("tool_name"))


if __name__ == "__main__":
    # Example usage for testing the ComputerManager and CommandRouter

    test_command_router()

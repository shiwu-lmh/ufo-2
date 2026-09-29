# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Rich Console Presenter

This module implements the Rich-based presenter for beautiful console output.
All agents' print_response logic is centralized here for maintainability.
"""

import json
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .base_presenter import BasePresenter

# Import response types for type hints
if TYPE_CHECKING:
    from ufo.agents.processors.schemas.response_schema import (
        AppAgentResponse,
        HostAgentResponse,
        EvaluationAgentResponse,
    )


class RichPresenter(BasePresenter):
    """
    Rich-based presenter for beautiful console output.

    This presenter uses the Rich library to create visually appealing
    console output with colors, panels, and tables.
    """

    # Style configuration - centralized for easy maintenance
    STYLES = {
        "thought": {"title": "💡 Thoughts", "style": "green"},
        "observation": {"title": "👀 Observations", "style": "bright_cyan"},
        "action": {"title": "⚒️ Actions", "style": "blue"},
        "action_applied": {"title": "⚒️ Action applied", "style": "blue"},
        "plan": {"title": "📚 Plans", "style": "cyan"},
        "next_plan": {"title": "📚 Next Plan", "style": "cyan"},
        "comment": {"title": "💬 Agent Comment", "style": "yellow"},
        "message": {"title": "📩 Messages to AppAgent", "style": "cyan"},
        "results": {"title": "📊 Current Task Results", "style": "bright_magenta"},
        "task_details": {"title": "📋 Task Details", "style": "yellow"},
        "dependencies": {"title": "🔗 Dependencies", "style": "blue"},
        "notice": {"title": "Notice", "style": "yellow"},
        "next_application": {
            "title": "📲 Next Selected Application/Agent",
            "style": "yellow",
        },
        "status_default": {"title": "📊 Status", "style": "blue"},
        "status_processing": {"title": "📊 Processing Status", "style": "blue"},
        "final_status": {"title": "📊 Final Status", "style": "yellow"},
        "status": {
            "FINISH": {"style": "green", "emoji": "✅"},
            "FAIL": {"style": "red", "emoji": "❌"},
            "CONTINUE": {"style": "yellow", "emoji": "🔄"},
            "START": {"style": "blue", "emoji": "🚀"},
        },
        # Evaluation-specific styles
        "evaluation": {
            "sub_scores": {"title": "📊 Sub-scores", "style": "green"},
            "task_complete": {"title": "💯 Task is complete", "style": "cyan"},
            "reason": {"title": "🤔 Reason", "style": "blue"},
        },
        # Response separator styles
        "separator": {
            "start": {"char": "═", "style": "bright_blue bold"},
            "end": {"char": "─", "style": "dim"},
        },
    }

    def __init__(self, console: Optional[Console] = None):
        """
        Initialize the Rich presenter.

        :param console: Optional Rich Console instance. If not provided, a new one is created.
        """
        self.console = console or Console()

    def _safe_text(self, text: str) -> str:
        """
        Avoid UnicodeEncodeError on legacy Windows consoles by stripping non-ASCII.
        """
        encoding = (self.console.encoding or "").lower()
        if "utf" in encoding:
            return text
        return text.encode("ascii", "ignore").decode("ascii")

    def present_response(self, response: Any, **kwargs) -> None:
        """
        Present the complete agent response.
        Delegates to specific methods based on response type.

        :param response: The response object to present
        :param kwargs: Additional options like print_action, etc.
        """
        # This is a generic method that will be overridden by specific presenter methods
        # or can delegate to type-specific presentation methods
        pass

    def present_thought(self, thought: str) -> None:
        """
        Present agent's thought/reasoning.

        :param thought: The thought text to display
        """
        if thought:
            self.console.print(
                Panel(
                    self._safe_text(thought),
                    title=self._safe_text(self.STYLES["thought"]["title"]),
                    style=self.STYLES["thought"]["style"],
                )
            )

    def present_observation(self, observation: str) -> None:
        """
        Present agent's observation.

        :param observation: The observation text to display
        """
        if observation:
            self.console.print(
                Panel(
                    self._safe_text(observation),
                    title=self._safe_text(self.STYLES["observation"]["title"]),
                    style=self.STYLES["observation"]["style"],
                )
            )

    def present_status(self, status: str, **kwargs) -> None:
        """
        Present agent's status.

        :param status: The status string
        :param kwargs: Optional 'title_style' to choose between different title styles
        """
        status_upper = status.upper()
        style_config = self.STYLES["status"].get(status_upper, {})
        emoji = style_config.get("emoji", "📊")
        style = style_config.get("style", "blue")

        title_style = kwargs.get("title_style", "processing")
        if title_style == "default":
            title = self.STYLES["status_default"]["title"]
        elif title_style == "final":
            title = self.STYLES["final_status"]["title"]
        else:
            title = (
                f"{emoji} {self.STYLES['status_processing']['title'].split(' ', 1)[-1]}"
            )

        self.console.print(
            Panel(
                self._safe_text(status_upper),
                title=self._safe_text(title),
                style=style,
            )
        )

    def present_actions(self, actions: Any, **kwargs) -> None:
        """
        Present agent's planned actions.

        :param actions: The actions to display
        :param kwargs: Display options like 'format' (table/list)
        """
        # This will be implemented by specific action presentation methods
        pass

    def present_action_list(self, actions: Any, success_only: bool = False) -> None:
        """
        Present action list with enhanced visual formatting.

        :param actions: ListActionCommandInfo object
        :param success_only: Whether to print only successful actions
        """
        from rich.rule import Rule
        from aip.messages import ResultStatus

        if not actions or not actions.actions:
            self.console.print(
                self._safe_text("ℹ️  No actions to display"), style="dim"
            )
            return

        # Filter actions based on success_only
        filtered_actions = [
            action
            for action in actions.actions
            if not success_only or action.result.status == ResultStatus.SUCCESS
        ]

        if not filtered_actions:
            self.console.print(
                self._safe_text("ℹ️  No actions to display"), style="dim"
            )
            return

        # Count successful and failed actions
        success_count = sum(
            1 for a in actions.actions if a.result.status == ResultStatus.SUCCESS
        )
        failed_count = len(actions.actions) - success_count

        # Print header
        self.console.print()
        header_text = f"⚒️  Action Execution Results ({len(filtered_actions)} action{'s' if len(filtered_actions) != 1 else ''})"
        encoding = (self.console.encoding or "").lower()
        header_char = "═" if "utf" in encoding else "="
        self.console.print(
            Rule(
                self._safe_text(header_text),
                style="bright_blue bold",
                characters=header_char,
            )
        )

        # Display each action with enhanced formatting
        for idx, action in enumerate(filtered_actions, 1):
            self._print_single_action(idx, action)

        # Display summary
        self._print_action_summary(success_count, failed_count, actions.status)

        # Print footer
        footer_char = "─" if "utf" in encoding else "-"
        self.console.print(
            Rule(
                style="dim",
                characters=footer_char,
            )
        )
        self.console.print()

    def present_plan(self, plan: List[str]) -> None:
        """
        Present agent's plan.

        :param plan: List of plan items
        """
        if plan:
            plan_str = "\n".join(plan) if isinstance(plan, list) else str(plan)
            self.console.print(
                Panel(
                    self._safe_text(plan_str),
                    title=self._safe_text(self.STYLES["next_plan"]["title"]),
                    style=self.STYLES["next_plan"]["style"],
                )
            )

    def present_comment(self, comment: Optional[str]) -> None:
        """
        Present agent's comment/message.

        :param comment: The comment text to display
        """
        if comment:
            self._display_agent_comment(comment)

    def _display_agent_comment(self, comment: str) -> None:
        """Display an agent comment using the shared Rich comment style."""
        if comment:
            self.console.print(
                Panel(
                    self._safe_text(comment),
                    title=self._safe_text(self.STYLES["comment"]["title"]),
                    style=self.STYLES["comment"]["style"],
                )
            )

    def present_results(self, results: Any) -> None:
        """
        Present execution results.

        :param results: The results to display
        """
        if results:
            results_content = str(results)
            if len(results_content) > 500:
                results_content = results_content[:497] + "..."

            self.console.print(
                Panel(
                    self._safe_text(results_content),
                    title=self._safe_text(self.STYLES["results"]["title"]),
                    style=self.STYLES["results"]["style"],
                )
            )

    # ============================================================================
    # Helper methods for visual separation
    # ============================================================================

    def _print_response_header(self, agent_type: str) -> None:
        """
        Print response header separator.

        :param agent_type: Agent type name (e.g., "AppAgent", "HostAgent")
        """
        from rich.rule import Rule

        start_char = self.STYLES["separator"]["start"]["char"]
        encoding = (self.console.encoding or "").lower()
        if "utf" not in encoding:
            start_char = "="

        self.console.print()
        self.console.print(
            Rule(
                self._safe_text(f"🤖 {agent_type} Response"),
                style=self.STYLES["separator"]["start"]["style"],
                characters=start_char,
            )
        )

    def _print_response_footer(self) -> None:
        """
        Print response footer separator.
        """
        from rich.rule import Rule

        end_char = self.STYLES["separator"]["end"]["char"]
        encoding = (self.console.encoding or "").lower()
        if "utf" not in encoding:
            end_char = "-"

        self.console.print(
            Rule(
                style=self.STYLES["separator"]["end"]["style"],
                characters=end_char,
            )
        )
        self.console.print()

    # ============================================================================
    # AppAgent-specific presentation methods
    # ============================================================================

    def present_app_agent_response(
        self, response: "AppAgentResponse", print_action: bool = True
    ) -> None:
        """
        Present AppAgent response - matches original AppAgent.print_response logic.

        :param response: AppAgentResponse object
        :param print_action: Whether to print actions
        """
        from ufo.agents.processors.schemas.actions import ActionCommandInfo

        # Print response header
        self._print_response_header("AppAgent")

        actions = response.action
        if isinstance(actions, ActionCommandInfo):
            actions = [actions]

        observation = response.observation
        thought = response.thought
        plan = response.plan if isinstance(response.plan, list) else [response.plan]
        comment = response.comment
        result = response.result

        # Observations
        self.present_observation(observation)

        # Thoughts
        self.present_thought(thought)

        # Actions as table
        if print_action and actions:
            self._present_actions_as_table(actions)

        # Next Plan
        self.present_plan(plan)

        # Comment
        self.present_comment(comment)

        # Screenshot saving
        screenshot_saving = response.save_screenshot
        if screenshot_saving.get("save", False):
            reason = screenshot_saving.get("reason")
            self.console.print(
                Panel(
                    self._safe_text(
                        f"📸 Screenshot saved to the blackboard.\nReason: {reason}"
                    ),
                    title=self._safe_text(self.STYLES["notice"]["title"]),
                    style=self.STYLES["notice"]["style"],
                )
            )
        # Results
        if result:
            self.present_results(result)

        # Print response footer
        self._print_response_footer()

    def _present_actions_as_table(self, actions: List[Any]) -> None:
        """
        Present actions as a Rich table (AppAgent style).

        :param actions: List of ActionCommandInfo objects
        """
        table = Table(
            title=self.STYLES["action"]["title"], show_lines=True, style="blue"
        )
        table.add_column("Step", style="cyan", no_wrap=True)
        table.add_column("Function", style="yellow")
        table.add_column("Arguments", style="magenta")
        table.add_column("Status", style="red")

        for i, action in enumerate(actions):
            args = action.arguments
            if isinstance(args, dict):
                args_str = str(args)
            else:
                args_str = str(json.loads(args))

            table.add_row(
                f"{i+1}",
                str(action.function),
                args_str,
                str(action.status),
            )

        self.console.print(table)

    # ============================================================================
    # HostAgent-specific presentation methods
    # ============================================================================

    def present_host_agent_response(
        self, response: "HostAgentResponse", action_str: Optional[str] = None
    ) -> None:
        """
        Present HostAgent response - matches original HostAgent.print_response logic.

        :param response: HostAgentResponse object
        :param action_str: Pre-formatted action string (optional)
        """
        # Print response header
        self._print_response_header("HostAgent")

        function = response.function
        arguments = response.arguments
        observation = response.observation
        thought = response.thought
        subtask = response.current_subtask
        result = response.result
        message = "\n".join(response.message) if response.message else ""
        plan = [subtask] + list(response.plan)
        plan_str = "\n".join([f"({i+1}) {str(item)}" for i, item in enumerate(plan)])
        status = response.status
        comment = response.comment

        application = (
            arguments.get("name") if function == "select_application_window" else None
        )

        # Observations
        self.present_observation(observation)

        # Thoughts
        self.present_thought(thought)

        # Action - use pre-formatted action string if provided, otherwise format it
        if function:
            if not action_str:
                action_str = self._format_action_string(function, arguments)

            self.console.print(
                Panel(
                    self._safe_text(action_str),
                    title=self._safe_text(self.STYLES["action_applied"]["title"]),
                    style=self.STYLES["action_applied"]["style"],
                )
            )

        # Plan
        self.console.print(
            Panel(
                self._safe_text(plan_str),
                title=self._safe_text(self.STYLES["plan"]["title"]),
                style=self.STYLES["plan"]["style"],
            )
        )

        # Next selected application
        if application:
            self.console.print(
                Panel(
                    self._safe_text(application),
                    title=self._safe_text(self.STYLES["next_application"]["title"]),
                    style=self.STYLES["next_application"]["style"],
                )
            )

        # Messages
        if message:
            self.console.print(
                Panel(
                    self._safe_text(message),
                    title=self._safe_text(self.STYLES["message"]["title"]),
                    style=self.STYLES["message"]["style"],
                )
            )

        # Status
        self.console.print(
            Panel(
                self._safe_text(status),
                title=self._safe_text(self.STYLES["status_default"]["title"]),
                style=self.STYLES["status_default"]["style"],
            )
        )

        # Comment
        self.present_comment(comment)

        # Results
        if result:
            self.present_results(result)

        # Print response footer
        self._print_response_footer()

    def _format_action_string(self, function: str, arguments: Dict[str, Any]) -> str:
        """
        Format action string for display.

        :param function: Function name
        :param arguments: Function arguments
        :return: Formatted action string
        """
        # Basic formatting - can be enhanced based on HostAgent.get_command_string
        args_str = ", ".join([f"{k}={v}" for k, v in arguments.items()])
        return f"{function}({args_str})"

    # ============================================================================
    def _print_single_action(self, idx: int, action: Any) -> None:
        """
        Print a single action with detailed information and visual formatting.

        :param idx: Action index number
        :param action: ActionCommandInfo object
        """
        from rich.text import Text
        from aip.messages import ResultStatus

        # Determine status icon and color
        encoding = (self.console.encoding or "").lower()
        action_result = getattr(action, "result", None)
        action_status = getattr(action_result, "status", None)
        function = getattr(action, "function", "")
        if not isinstance(function, str):
            function = ""

        if action_status == ResultStatus.SUCCESS:
            status_icon = "✅" if "utf" in encoding else "OK"
            status_color = "green"
            border_style = "green"
        elif action_status == ResultStatus.FAILURE:
            status_icon = "❌" if "utf" in encoding else "FAIL"
            status_color = "red"
            border_style = "red"
        else:
            status_icon = "⏸️" if "utf" in encoding else "WAIT"
            status_color = "yellow"
            border_style = "yellow"

        # Build content with proper formatting
        content = Text()

        # Function
        content.append("Function: ", style="cyan bold")
        content.append(
            f"{function}\n" if function else "[dim]None[/dim]\n",
            style="white",
        )

        # Arguments
        arguments = getattr(action, "arguments", {})
        if isinstance(arguments, dict) and arguments:
            args_str = ", ".join([f"{k}={v}" for k, v in arguments.items()])
            if len(args_str) > 100:
                args_str = args_str[:97] + "..."
            content.append("Arguments: ", style="cyan bold")
            content.append(f"{args_str}\n", style="white")

        # Target information
        target = getattr(action, "target", None)
        if target:
            target_name = str(
                getattr(target, "name", None) or getattr(target, "id", None) or "Unknown"
            )
            target_type = str(getattr(target, "type", None) or "Unknown")
            content.append("Target: ", style="cyan bold")
            content.append(f"{target_name} ", style="white")
            content.append(f"({target_type})\n", style="dim")

        # Status
        status_text = getattr(action_status, "value", action_status) or "UNKNOWN"
        content.append("Status: ", style="cyan bold")
        content.append(f"{status_icon} {str(status_text).upper()}", style=status_color)

        # Create panel for this action
        panel_title = f"[bold]Action #{idx}[/bold]"
        self.console.print(
            Panel(
                content,
                title=panel_title,
                border_style=border_style,
                padding=(0, 1),
            )
        )

        # Show result details if available
        result_value = getattr(action_result, "result", None)
        if result_value and str(result_value).strip():
            result_text = Text()
            if "utf" in (self.console.encoding or "").lower():
                result_prefix = "    └─ Result: "
            else:
                result_prefix = "    - Result: "
            result_text.append(result_prefix, style="dim")
            result_str = str(result_value)
            if len(result_str) > 500:
                result_str = result_str[:497] + "..."
            result_text.append(self._safe_text(result_str), style="bright_black")
            self.console.print(result_text)

        # Show error if failed
        error_value = getattr(action_result, "error", None)
        if action_status == ResultStatus.FAILURE and error_value:
            error_text = Text()
            if "utf" in (self.console.encoding or "").lower():
                error_prefix = "    └─ Error: "
            else:
                error_prefix = "    - Error: "
            error_text.append(error_prefix, style="red dim")
            error_str = str(error_value)
            if len(error_str) > 100:
                error_str = error_str[:97] + "..."
            error_text.append(self._safe_text(error_str), style="red")
            self.console.print(error_text)

    def _print_action_summary(
        self, success_count: int, failed_count: int, status: str
    ) -> None:
        """
        Print summary of action execution results.

        :param success_count: Number of successful actions
        :param failed_count: Number of failed actions
        :param status: Overall execution status
        """
        from rich.panel import Panel

        summary = Table(show_header=False, box=None, padding=(0, 2))
        summary.add_column("Label", style="bold")
        summary.add_column("Value")

        encoding = (self.console.encoding or "").lower()
        success_label = "✅ Successful:" if "utf" in encoding else "Successful:"
        failed_label = "❌ Failed:" if "utf" in encoding else "Failed:"
        status_label = "📊 Status:" if "utf" in encoding else "Status:"

        # Success count
        if success_count > 0:
            success_text = Text()
            success_text.append(str(success_count), style="green bold")
            success_text.append(" succeeded", style="green")
            summary.add_row(success_label, success_text)

        # Failed count
        if failed_count > 0:
            failed_text = Text()
            failed_text.append(str(failed_count), style="red bold")
            failed_text.append(" failed", style="red")
            summary.add_row(failed_label, failed_text)

        # Final status
        status_style = "green" if status in ["FINISH", "COMPLETED"] else "yellow"
        if "utf" in encoding:
            status_emoji = "🏁" if status == "FINISH" else "🔄"
            status_text = Text(f"{status_emoji} {status}", style=f"{status_style} bold")
        else:
            status_text = Text(f"{status}", style=f"{status_style} bold")
        summary.add_row(status_label, status_text)

        self.console.print()
        self.console.print(
            Panel(summary, title="Summary", border_style="blue", padding=(0, 1))
        )

    # ============================================================================

    # EvaluationAgent-specific presentation methods
    # ============================================================================

    def present_evaluation_agent_response(
        self, response: "EvaluationAgentResponse"
    ) -> None:
        """
        Present EvaluationAgent response - matches original EvaluationAgent.print_response logic.

        :param response: EvaluationAgentResponse object
        """
        from rich.rule import Rule

        # Print response header
        self._print_response_header("EvaluationAgent")

        if "utf" in (self.console.encoding or "").lower():
            emoji_map = {
                "yes": "✅",
                "no": "❌",
                "unsure": "❓",
            }
        else:
            emoji_map = {
                "yes": "YES",
                "no": "NO",
                "unsure": "UNSURE",
            }

        complete = emoji_map.get(response.complete, response.complete)
        sub_scores = response.sub_scores or []
        reason = response.reason

        # Sub-scores table
        if sub_scores:
            table = Table(
                title=self._safe_text(self.STYLES["evaluation"]["sub_scores"]["title"]),
                show_lines=True,
                style=self.STYLES["evaluation"]["sub_scores"]["style"],
            )
            table.add_column("Metric", style="cyan", no_wrap=True)
            table.add_column("Evaluation", style="green")
            for sub_score in sub_scores:
                score = sub_score.get("name")
                evaluation = sub_score.get("evaluation")
                table.add_row(str(score), str(emoji_map.get(evaluation, evaluation)))
            self.console.print(table)

        # Task complete
        self.console.print(
            Panel(
                self._safe_text(f"{complete}"),
                title=self._safe_text(self.STYLES["evaluation"]["task_complete"]["title"]),
                style=self.STYLES["evaluation"]["task_complete"]["style"],
            )
        )

        # Reason
        if reason:
            self.console.print(
                Panel(
                    self._safe_text(reason),
                    title=self._safe_text(self.STYLES["evaluation"]["reason"]["title"]),
                    style=self.STYLES["evaluation"]["reason"]["style"],
                )
            )

        # Print response footer
        self._print_response_footer()

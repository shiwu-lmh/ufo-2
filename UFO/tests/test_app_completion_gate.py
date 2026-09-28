from types import SimpleNamespace

from aip.messages import Result, ResultStatus

# Mirror the application's normal import order to avoid the processor modules'
# documented registration-time circular import.
import ufo.agents.processors.app_agent_processor  # noqa: F401
from ufo.agents.processors.strategies.app_agent_processing_strategy import (
    AppActionExecutionStrategy,
)


def _memory_item(subtask, actions, completion_gate=""):
    return {
        "subtask": subtask,
        "action": actions,
        "completion_gate": completion_gate,
    }


def _action(status):
    return {"function": "click_input", "result": {"status": status}}


def _agent_with_memory(*items):
    return SimpleNamespace(
        memory=SimpleNamespace(
            filter_memory_from_keys=lambda keys: [
                {key: item[key] for key in keys if key in item}
                for item in items
            ]
        )
    )


def test_no_action_finish_without_subtask_evidence_is_downgraded():
    status, reason = AppActionExecutionStrategy.resolve_completion_status(
        requested_status="FINISH",
        has_action_this_turn=False,
        has_subtask_action_evidence=False,
        execution_results=[],
    )

    assert status == "CONTINUE"
    assert "evidence" in reason.lower()


def test_failed_tool_result_cannot_be_reported_as_finish():
    status, reason = AppActionExecutionStrategy.resolve_completion_status(
        requested_status="FINISH",
        has_action_this_turn=True,
        has_subtask_action_evidence=True,
        execution_results=[
            Result(status=ResultStatus.FAILURE, error="blocked", result=None)
        ],
    )

    assert status == "CONTINUE"
    assert "failed" in reason.lower()


def test_scroll_bottom_signal_cannot_override_a_failed_action():
    status, _reason = AppActionExecutionStrategy.resolve_completion_status(
        requested_status="FINISH",
        has_action_this_turn=True,
        has_subtask_action_evidence=True,
        execution_results=[
            Result(
                status=ResultStatus.FAILURE,
                error="blocked",
                result="scroll_state: at_bottom=true",
            )
        ],
        reached_scroll_bottom=True,
    )

    assert status == "CONTINUE"


def test_successful_action_in_current_subtask_allows_later_no_action_finish():
    agent = _agent_with_memory(
        _memory_item("calculate 1083", [_action("success")]),
        _memory_item("calculate 130", [_action("success")]),
    )

    assert AppActionExecutionStrategy.has_subtask_action_evidence(
        agent, "calculate 1083"
    )
    assert not AppActionExecutionStrategy.has_subtask_action_evidence(
        agent, "calculate 1213"
    )


def test_action_evidence_accepts_runtime_result_status_enum():
    agent = _agent_with_memory(
        _memory_item("calculate 1083", [_action(ResultStatus.SUCCESS)])
    )

    assert AppActionExecutionStrategy.has_subtask_action_evidence(
        agent, "calculate 1083"
    )


def test_failure_after_success_clears_subtask_completion_evidence():
    agent = _agent_with_memory(
        _memory_item("reopen file", [_action("success")]),
        _memory_item("reopen file", [_action("failure")]),
    )

    assert not AppActionExecutionStrategy.has_subtask_action_evidence(
        agent, "reopen file"
    )


def test_unverified_finish_attempts_are_counted_per_subtask():
    agent = _agent_with_memory(
        _memory_item("calculate 130", [], completion_gate="unverified_finish"),
        _memory_item("calculate 1083", [], completion_gate="unverified_finish"),
        _memory_item("calculate 130", [], completion_gate="execution_failure"),
    )

    assert (
        AppActionExecutionStrategy.unverified_finish_count(agent, "calculate 130")
        == 1
    )


def test_unverified_finish_attempts_count_the_runtime_gate_message():
    gate_message = (
        "unverified_finish: no successful action evidence yet; "
        "do not finish until a fresh UI observation supports the subtask result."
    )
    agent = _agent_with_memory(
        _memory_item("calculate 1083", [], completion_gate=gate_message),
        _memory_item("calculate 1083", [], completion_gate=gate_message),
    )

    attempts = AppActionExecutionStrategy.unverified_finish_count(
        agent, "calculate 1083"
    )
    status, reason = AppActionExecutionStrategy.resolve_completion_status(
        requested_status="FINISH",
        has_action_this_turn=False,
        has_subtask_action_evidence=False,
        execution_results=[],
        unverified_finish_attempts=attempts,
        max_unverified_finish_attempts=2,
    )

    assert attempts == 2
    assert status == "ERROR"
    assert "allowed recovery attempts" in reason


def test_unverified_finish_attempts_can_be_bounded():
    status, reason = AppActionExecutionStrategy.resolve_completion_status(
        requested_status="FINISH",
        has_action_this_turn=False,
        has_subtask_action_evidence=False,
        execution_results=[],
        unverified_finish_attempts=2,
        max_unverified_finish_attempts=2,
    )

    assert status == "ERROR"
    assert "verification" in reason.lower()


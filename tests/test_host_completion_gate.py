from ufo.agents.processors.strategies.host_agent_processing_strategy import (
    HostActionExecutionStrategy,
)


def test_host_cannot_finish_while_a_subtask_failure_is_unresolved():
    previous_subtasks = [
        {"subtask": "calculate second formula", "status": "ERROR"},
        {"subtask": "write report", "status": "FINISH"},
    ]

    assert HostActionExecutionStrategy.has_unresolved_subtask_failures(
        previous_subtasks
    )
    assert (
        HostActionExecutionStrategy.resolve_terminal_status(
            "FINISH", "no_action", previous_subtasks
        )
        == "ERROR"
    )


def test_successful_retry_resolves_matching_failed_subtask():
    previous_subtasks = [
        {"subtask": "reopen saved file", "status": "ERROR"},
        {"subtask": "reopen saved file", "status": "FINISH"},
    ]

    assert not HostActionExecutionStrategy.has_unresolved_subtask_failures(
        previous_subtasks
    )
    assert (
        HostActionExecutionStrategy.resolve_terminal_status(
            "FINISH", "no_action", previous_subtasks
        )
        == "FINISH"
    )

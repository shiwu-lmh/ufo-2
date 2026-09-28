from types import SimpleNamespace
import unittest

from ufo.agents.processors.context.processing_context import (
    ProcessingPhase,
    ProcessingResult,
)
from ufo.agents.processors.core.processor_framework import ProcessorTemplate


class _FailingStrategy:
    name = "failing_strategy"

    async def execute(self, _agent, _context):
        return ProcessingResult(
            success=False,
            data={},
            error="selected application window is stale",
        )


class _StoppingStrategy:
    name = "stopping_strategy"

    async def execute(self, _agent, _context):
        return ProcessingResult(
            success=True,
            data={"stop_processing": True, "status": "FINISH"},
        )


class _ShouldNotRunStrategy:
    name = "should_not_run_strategy"

    def __init__(self):
        self.called = False

    async def execute(self, _agent, _context):
        self.called = True
        return ProcessingResult(success=True, data={})


class _Processor(ProcessorTemplate):
    def _setup_strategies(self):
        self.strategies = {ProcessingPhase.DATA_COLLECTION: _FailingStrategy()}

    def _setup_middleware(self):
        self.middleware_chain = []

    def _get_processor_specific_context_data(self):
        return {}

    def _get_common_context_data(self):
        return {"agent_type": "test"}


class ProcessorFailureStatusTests(unittest.IsolatedAsyncioTestCase):
    async def test_failed_strategy_sets_processor_result_and_agent_status_to_error(
        self,
    ):
        processor = _Processor(
            agent=SimpleNamespace(name="test-agent"),
            global_context=SimpleNamespace(
                command_dispatcher=None,
                get=lambda *_args: None,
                set=lambda *_args: None,
            ),
        )

        result = await processor.process()

        self.assertFalse(result.success)
        self.assertIn("stale", result.error)
        self.assertEqual(
            processor.processing_context.get_local("status"), "ERROR"
        )

    async def test_stop_processing_handoff_skips_later_phases(self):
        processor = _Processor(
            agent=SimpleNamespace(name="test-agent"),
            global_context=SimpleNamespace(
                command_dispatcher=None,
                get=lambda *_args: None,
                set=lambda *_args: None,
            ),
        )
        later = _ShouldNotRunStrategy()
        processor.strategies = {
            ProcessingPhase.DATA_COLLECTION: _StoppingStrategy(),
            ProcessingPhase.LLM_INTERACTION: later,
        }

        result = await processor.process()

        self.assertFalse(later.called)
        self.assertTrue(result.data["processing_stopped_early"])
        self.assertEqual(
            processor.processing_context.get_local("status"), "FINISH"
        )

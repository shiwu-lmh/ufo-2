import unittest
from unittest.mock import patch

from ufo.agents.processors.schemas.actions import ActionCommandInfo
from ufo.agents.processors.schemas.target import TargetInfo, TargetKind
from ufo.automator.action_execution import ActionExecutor


class ActionExecutionTests(unittest.TestCase):
    def test_stale_control_error_uses_action_representation_value(self):
        action = ActionCommandInfo(
            function="click_input",
            target=TargetInfo(
                kind=TargetKind.CONTROL,
                name="Old button",
                id="7",
                type="Button",
            ),
            action_representation="click_input(id='7')",
        )

        with patch.object(ActionExecutor, "_control_validation", return_value=False):
            with self.assertRaisesRegex(ValueError, "click_input\(id='7'\)"):
                ActionExecutor().execute(action, None, {"7": object()})


if __name__ == "__main__":
    unittest.main()

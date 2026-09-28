"""Regression tests for tolerant AppAgent response parsing."""

from ufo.agents.processors.schemas.response_schema import AppAgentResponse


def test_boolean_save_screenshot_is_normalized_to_configuration_dict():
    """Qwen may emit false instead of the structured screenshot configuration."""
    response = AppAgentResponse.model_validate(
        {
            "observation": "Calculator is visible.",
            "thought": "Continue with the requested calculation.",
            "save_screenshot": False,
        }
    )

    assert response.save_screenshot == {"save": False, "reason": ""}


def test_true_save_screenshot_preserves_a_positive_request():
    response = AppAgentResponse.model_validate(
        {
            "observation": "The result is visible.",
            "thought": "Save this state as evidence.",
            "save_screenshot": True,
        }
    )

    assert response.save_screenshot == {"save": True, "reason": ""}

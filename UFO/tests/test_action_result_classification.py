from types import SimpleNamespace

from ufo.client.computer import CommandRouter


def test_control_name_warning_is_not_treated_as_success():
    result = SimpleNamespace(
        is_error=False,
        data=(
            "Warning: The name of your chosen control id 134 is "
            "详细版入职指引：20260805.docx, but the name argument is 文字."
        ),
        content=[],
    )

    assert not CommandRouter._is_successful_action_result([result])


def test_normal_click_result_is_successful():
    result = SimpleNamespace(
        is_error=False,
        data="Click action has been executed, with parameters: {'button': 'left'}",
        content=[],
    )

    assert CommandRouter._is_successful_action_result([result])


def test_coordinate_clicks_use_the_same_retry_and_state_verification_path():
    assert "click_on_coordinates" in CommandRouter._COORDINATE_ACTIONS


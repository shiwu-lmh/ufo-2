from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_app_prompt_recovers_from_blocked_shell_file_open_via_ui():
    prompt = (REPO_ROOT / "ufo/prompts/share/base/app_agent.yaml").read_text(
        encoding="utf-8"
    )

    assert "native Open dialog" in prompt
    assert "verify the reopened document" in prompt
    assert "Do not claim the file was reopened" in prompt


def test_host_prompt_does_not_launch_file_paths_through_shell():
    prompt = (REPO_ROOT / "ufo/prompts/share/base/host_agent.yaml").read_text(
        encoding="utf-8"
    )

    assert "use the application's native Open dialog" in prompt
    assert "Do not report overall FINISH" in prompt

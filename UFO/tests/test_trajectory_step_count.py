from ufo.trajectory.parser import Trajectory


def test_step_number_uses_session_step_schema():
    trajectory = Trajectory.__new__(Trajectory)
    trajectory._step_log = [
        {"agent_type": "AppAgent", "session_step": 0},
        {"agent_type": "AppAgent", "session_step": 49},
        {"agent_type": "HostAgent", "round_step": 51},
    ]

    assert trajectory.step_number == 52


def test_round_number_uses_round_num_schema():
    trajectory = Trajectory.__new__(Trajectory)
    trajectory._step_log = [
        {"round_num": 0},
        {"round_num": 1},
    ]

    assert trajectory.round_number == 2

import harness_input


def test_clean_keeps_text_and_newlines() -> None:
    assert harness_input.clean("  line one\r\nline\ttwo\n") == "line one\nline\ttwo"


def test_clean_strips_escape_sequences_and_control_keys() -> None:
    # ESC[201~ would end the bracketed paste early; ^C would interrupt the session.
    assert harness_input.clean("hi\x1b[201~\x03\x7f\x9b") == "hi[201~"


def test_session_environment_drops_uv_run_activation() -> None:
    # What `uv run --project ~/kb` injects into kb's own process (seen on 2026-10-15).
    env = {
        "PATH": "/home/u/kb/.venv/bin:/home/u/bin:/usr/bin",
        "VIRTUAL_ENV": "/home/u/kb/.venv",
        "UV": "/home/u/.local/bin/uv",
        "UV_RUN_RECURSION_DEPTH": "1",
        "HOME": "/home/u",
    }
    assert harness_input.session_environment(env) == {
        "PATH": "/home/u/bin:/usr/bin",
        "HOME": "/home/u",
    }


def test_session_environment_without_a_venv_is_unchanged() -> None:
    env = {"PATH": "/home/u/bin:/usr/bin", "HOME": "/home/u"}
    assert harness_input.session_environment(env) == env

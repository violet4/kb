import harness_input


def test_clean_keeps_text_and_newlines() -> None:
    assert harness_input.clean("  line one\r\nline\ttwo\n") == "line one\nline\ttwo"


def test_clean_strips_escape_sequences_and_control_keys() -> None:
    # ESC[201~ would end the bracketed paste early; ^C would interrupt the session.
    assert harness_input.clean("hi\x1b[201~\x03\x7f\x9b") == "hi[201~"

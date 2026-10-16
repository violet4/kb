"""Heredoc bodies are data, not commands: hooks that read a command's text skip them, so a
commit message or a file's contents never looks like a command or a redirect."""

from kb_cli.shell_command import without_heredoc_bodies

COMMAND = """git commit -F - <<'EOF'
mentions uv sync and echo x > y.md
EOF
uv sync
cat > a.md <<EOF2
body > b.md
EOF2
echo done > c.md
"""


def test_heredoc_bodies_are_removed_and_their_opening_lines_kept() -> None:
    stripped = without_heredoc_bodies(COMMAND)
    assert "mentions" not in stripped and "body > b.md" not in stripped
    assert "git commit -F - <<'EOF'" in stripped
    assert "cat > a.md <<EOF2" in stripped
    assert "uv sync" in stripped.split("<<'EOF'", 1)[1]
    assert "echo done > c.md" in stripped


def test_dash_heredoc_ends_at_a_tab_indented_word() -> None:
    assert without_heredoc_bodies("cat <<-END\n\tsecret > x\n\tEND\nls\n") == "cat <<-END\n\nls\n"


def test_unterminated_heredoc_is_kept() -> None:
    # Without its terminator line it may not be a heredoc; keeping the text checks more.
    assert without_heredoc_bodies("cat <<EOF\nuv sync\n") == "cat <<EOF\nuv sync\n"


def test_here_string_and_shift_are_not_heredocs() -> None:
    for command in ['cat <<<"x"\nuv sync\nx\n', "echo $((1<<2))\nuv sync\n2\n"]:
        assert without_heredoc_bodies(command) == command


def test_command_without_heredoc_is_unchanged() -> None:
    assert without_heredoc_bodies("echo a > b && uv sync") == "echo a > b && uv sync"


def test_heredoc_fed_to_a_shell_or_interpreter_is_kept() -> None:
    # A body a shell or interpreter runs is code, not data.
    for command in [
        "bash <<'EOF'\nuv sync\nEOF\n",
        "cat <<EOF | sh\nuv sync\nEOF\n",
        "ssh host <<EOF\nuv sync\nEOF\n",
        "python3 - <<'EOF'\nimport os\nEOF\n",
    ]:
        assert without_heredoc_bodies(command) == command

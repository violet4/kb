"""Reading a Bash command's text as the commands it runs, for hooks that inspect a command
before it runs (kb_cli/hooks.py, kb_cli/required_reading.py)."""

import re

# `<<WORD`, `<<-WORD`, `<<'WORD'`, `<<"WORD"`, then the body up to a line holding only WORD
# (tab-indented for `<<-`). Not a here-string (`<<<`) or a shift (`1<<2`), and only a body
# whose terminator line is present: a hook reading the command checks more, never less, when
# unsure.
_HEREDOC_RE = re.compile(
    r"(?<![<\w])<<(?!<)(-?)[ \t]*(['\"]?)(\w+)\2([^\n]*\n)(.*?)^\t*\3[ \t]*$", re.DOTALL | re.MULTILINE
)

# A shell or script interpreter named anywhere on a heredoc's opening line (`bash <<EOF`,
# `cat <<EOF | sh`, `ssh host <<EOF`, `python3 - <<EOF`): the body is code that line runs.
_INTERPRETER_RE = re.compile(
    r"(?:^|[\s;&|(/])(?:(?:ba|z|da|k|fi)?sh|ssh|eval|source|python[\d.]*|node|perl|ruby)(?![\w.-])"
)


def _opening_line(match: re.Match[str]) -> str:
    """The whole line a heredoc starts on: the command before `<<` and the rest after WORD."""
    line_start = match.string.rfind("\n", 0, match.start()) + 1
    return match.string[line_start : match.start()] + match.group(4)


def without_heredoc_bodies(command: str) -> str:
    """`command` with each heredoc's body removed, keeping the line that opens it: a body is
    data fed to a command (a commit message, a file's contents), not commands, so text in it
    that looks like `uv sync` or a `> file` redirect is not one. A body fed to a shell or
    script interpreter is code that runs, so it is kept."""

    def strip_body(match: re.Match[str]) -> str:
        if _INTERPRETER_RE.search(_opening_line(match)):
            return match.group(0)
        return f"<<{match.group(1)}{match.group(2)}{match.group(3)}{match.group(2)}{match.group(4)}"

    return _HEREDOC_RE.sub(strip_body, command)

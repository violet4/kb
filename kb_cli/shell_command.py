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


def without_heredoc_bodies(command: str) -> str:
    """`command` with each heredoc's body removed, keeping the line that opens it: a body is
    data fed to a command (a commit message, a file's contents), not commands, so text in it
    that looks like `uv sync` or a `> file` redirect is not one."""
    return _HEREDOC_RE.sub(lambda m: f"<<{m.group(1)}{m.group(2)}{m.group(3)}{m.group(2)}{m.group(4)}", command)

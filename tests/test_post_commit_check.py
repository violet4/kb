"""post-commit-check recognizes a `git commit` run as a command, not the words "git commit"
appearing inside another command's arguments."""

import pytest

from kb_cli.hooks import _GIT_COMMIT_RE


@pytest.mark.parametrize(
    "command",
    [
        'git commit -m "x"',
        "cd ~/kb; git add a && git commit -q -F - <<'EOF'\nmsg\nEOF",
        "git -C ~/games/project_gorgon commit -F msg.txt",
        "git add -u\ngit commit --amend --no-edit",
        "(cd repo && git commit -m x)",
    ],
)
def test_git_commit_command_matches(command: str) -> None:
    assert _GIT_COMMIT_RE.search(command)


@pytest.mark.parametrize(
    "command",
    [
        'kb ab add URL "Title" "end each session with a git commit and a progress update"',
        "git log --grep='git commit'",
        "git commit-tree HEAD^{tree}",
        "echo legit commit",
    ],
)
def test_git_commit_words_in_arguments_do_not_match(command: str) -> None:
    assert not _GIT_COMMIT_RE.search(command)

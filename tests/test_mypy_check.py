"""mypy-check recognizes mypy's own failure summary, not another tool's similar line."""

from kb_cli.hooks import _MYPY_FAILURE_RE


def test_mypy_check_matches_mypy_failures_only() -> None:
    assert _MYPY_FAILURE_RE.search("Found 6 errors in 4 files (checked 171 source files)")
    assert _MYPY_FAILURE_RE.search("Found 1 error in 1 file (checked 1 source file)")
    assert not _MYPY_FAILURE_RE.search("Found 3 errors.\n[*] 2 fixable with the `--fix` option.")
    assert not _MYPY_FAILURE_RE.search("Success: no issues found in 211 source files")

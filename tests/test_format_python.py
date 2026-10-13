"""format-python formats a Python file only when its project configures black, and finds the
files a `text sub`/`text replace` command edited."""

from pathlib import Path

from kb_cli.hooks import _TEXT_EDIT_PY_RE, _black_project


def test_black_project_is_nearest_pyproject_with_black(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[tool.black]\nline-length = 120\n")
    (tmp_path / "pkg").mkdir()
    module = tmp_path / "pkg" / "m.py"
    module.write_text("")
    assert _black_project(module) == tmp_path


def test_nearest_pyproject_without_black_means_no_formatting(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[tool.black]\n")
    inner = tmp_path / "sub"
    inner.mkdir()
    (inner / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    module = inner / "m.py"
    module.write_text("")
    assert _black_project(module) is None


def test_text_edit_targets_are_python_files_only() -> None:
    command = "text sub --file a/b.py -i --expect 1 x y && text replace --file docs/c.md -i s e n"
    assert _TEXT_EDIT_PY_RE.findall(command) == ["a/b.py"]

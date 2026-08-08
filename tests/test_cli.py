"""Tests for the CLI foundation."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from cvflow import __version__
from cvflow.cli.main import (
    EXIT_LOAD_ERROR,
    EXIT_OK,
    EXIT_TARGET_NOT_FOUND,
    EXIT_USAGE,
    build_parser,
    main,
)


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == EXIT_OK
    out = capsys.readouterr().out
    assert __version__ in out


def test_no_command_prints_help_and_usage_exit(capsys: pytest.CaptureFixture[str]) -> None:
    code = main([])
    assert code == EXIT_USAGE
    out = capsys.readouterr().out
    assert "inspect" in out


def test_inspect_loads_and_summarizes(
    yolo_yaml_dataset: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["inspect", str(yolo_yaml_dataset)])
    assert code == EXIT_OK
    out = capsys.readouterr().out
    assert "YOLO dataset" in out
    assert "Images" in out
    assert "Annotations" in out
    assert "train" in out


def test_inspect_explicit_format(
    coco_dir_dataset: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["inspect", str(coco_dir_dataset), "--format", "coco"])
    assert code == EXIT_OK
    out = capsys.readouterr().out
    assert "COCO dataset" in out


def test_inspect_undetectable_dataset(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "readme.txt").write_text("not a dataset")
    code = main(["inspect", str(tmp_path)])
    assert code == EXIT_LOAD_ERROR
    err = capsys.readouterr().err
    assert "error" in err.lower()


def test_inspect_missing_path(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["inspect", "/nonexistent/path/for/cvflow/test"])
    assert code == EXIT_TARGET_NOT_FOUND
    err = capsys.readouterr().err
    assert "does not exist" in err


def test_parser_builds() -> None:
    parser = build_parser()
    args = parser.parse_args(["inspect", "."])
    assert args.command == "inspect"
    assert str(args.path) == "."


def test_module_entry_point(yolo_yaml_dataset: Path) -> None:
    # `python -m cvflow inspect <path>` should behave like the console script.
    result = subprocess.run(
        [sys.executable, "-m", "cvflow", "inspect", str(yolo_yaml_dataset)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == EXIT_OK
    assert __version__ in result.stdout

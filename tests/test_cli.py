"""Tests for the CLI foundation."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from cvflow import __version__
from cvflow.cli.main import (
    EXIT_ISSUES_FOUND,
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


def test_inspect_reports_health(clean_dataset: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # clean_dataset has valid images and only a WARNING -> exit OK, report shown.
    code = main(["inspect", str(clean_dataset)])
    assert code == EXIT_OK
    out = capsys.readouterr().out
    assert "CVFlow Dataset Health" in out
    assert "Health Summary" in out
    assert "train" in out


def test_inspect_explicit_format(
    coco_dir_dataset: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["inspect", str(coco_dir_dataset), "--format", "coco"])
    assert code == EXIT_OK
    out = capsys.readouterr().out
    assert "COCO" in out


def test_inspect_shows_and_hides_statistics(
    clean_dataset: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["inspect", str(clean_dataset)])
    assert "Dataset Statistics" in capsys.readouterr().out
    main(["inspect", str(clean_dataset), "--no-stats"])
    assert "Dataset Statistics" not in capsys.readouterr().out


def test_inspect_returns_nonzero_on_errors(
    integrity_dataset: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["inspect", str(integrity_dataset)])
    assert code == EXIT_ISSUES_FOUND
    out = capsys.readouterr().out
    assert "ERROR" in out


def test_inspect_no_images_flag_skips_corrupt(
    corrupt_only_dataset: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # With images checked, the corrupt image is an ERROR -> non-zero exit.
    code = main(["inspect", str(corrupt_only_dataset)])
    out = capsys.readouterr().out
    assert code == EXIT_ISSUES_FOUND
    assert "corrupt" in out.lower()

    # With --no-images, the corrupt check is skipped and nothing else is wrong.
    code = main(["inspect", str(corrupt_only_dataset), "--no-images"])
    out = capsys.readouterr().out
    assert code == EXIT_OK
    assert "corrupt" not in out.lower()


def test_inspect_strict_flag_fails_on_warnings(
    clean_dataset: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # clean_dataset has a background image -> empty-image WARNING, no ERRORs.
    assert main(["inspect", str(clean_dataset)]) == EXIT_OK
    capsys.readouterr()
    assert main(["inspect", str(clean_dataset), "--strict"]) == EXIT_ISSUES_FOUND
    capsys.readouterr()


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


def test_inspect_html_writes_dashboard(
    clean_dataset: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "reports" / "dashboard.html"
    code = main(["inspect", str(clean_dataset), "--html", str(out)])
    assert code == EXIT_OK

    html = out.read_text(encoding="utf-8")
    assert html.startswith("<!doctype html>")
    assert "cvflow-data" in html
    # The dashboard replaces the text report rather than printing alongside it.
    out_text = capsys.readouterr().out
    assert "CVFlow Dataset Health" not in out_text
    assert str(out) in out_text


def test_inspect_html_keeps_exit_code(
    integrity_dataset: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "dashboard.html"
    assert main(["inspect", str(integrity_dataset), "--html", str(out)]) == EXIT_ISSUES_FOUND
    capsys.readouterr()


def test_serve_flags_parse() -> None:
    parser = build_parser()
    args = parser.parse_args(
        ["inspect", ".", "--serve", "--port", "8123", "--host", "0.0.0.0", "--no-browser"]
    )
    assert args.serve is True
    assert args.port == 8123
    assert args.host == "0.0.0.0"
    assert args.open_browser is False


def test_parser_builds() -> None:
    parser = build_parser()
    args = parser.parse_args(["inspect", "."])
    assert args.command == "inspect"
    assert str(args.path) == "."


def test_module_entry_point(clean_dataset: Path) -> None:
    # `python -m cvflow inspect <path>` should behave like the console script,
    # including when stdout is a pipe on a non-UTF-8 console (Windows cp1252):
    # the report's box-drawing rules must not blow up the process.
    result = subprocess.run(
        [sys.executable, "-m", "cvflow", "inspect", str(clean_dataset)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == EXIT_OK, result.stderr
    assert "CVFlow Dataset Health" in result.stdout
    assert "─" in result.stdout  # the rule survived the pipe


def test_inspect_announces_the_wait(
    clean_dataset: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A silent terminal during a minutes-long scan looks like a hang."""
    main(["inspect", str(clean_dataset)])
    captured = capsys.readouterr()

    assert "1-5 minutes" in captured.err
    assert "Analyzing" in captured.err
    # It is progress, not output: piping the report must not pick it up.
    assert "Analyzing" not in captured.out


def test_inspect_note_is_honest_without_image_checks(
    clean_dataset: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["inspect", str(clean_dataset), "--no-images"])
    captured = capsys.readouterr()

    assert "quick" in captured.err
    assert "1-5 minutes" not in captured.err

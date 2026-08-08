"""CVFlow command-line entry point.

The ``inspect`` command loads a dataset, runs the analysis engine, and prints a
prioritized health report. Built on the standard-library :mod:`argparse` to keep
dependencies minimal; richer terminal output can be layered on later without
changing this surface.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from cvflow import __version__
from cvflow.analysis import AnalysisEngine, CheckConfig, default_checks
from cvflow.exceptions import DatasetError
from cvflow.loaders import available_formats, load_dataset
from cvflow.model import Severity
from cvflow.report import render_report

_PROG = "cvflow"

# Exit codes. These are part of the CLI contract that CI and scripts rely on,
# so they are defined once here and reused.
EXIT_OK = 0
EXIT_USAGE = 2
EXIT_TARGET_NOT_FOUND = 3
EXIT_LOAD_ERROR = 4
EXIT_ISSUES_FOUND = 1


def build_parser() -> argparse.ArgumentParser:
    """Construct the top-level argument parser and its subcommands."""
    parser = argparse.ArgumentParser(
        prog=_PROG,
        description=(
            "CVFlow — ESLint / DevTools for computer-vision datasets. "
            "Surface broken, duplicated, inconsistent, or suspicious data "
            "without inspecting thousands of images by hand."
        ),
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    inspect = subparsers.add_parser(
        "inspect",
        help="Analyze a dataset and report integrity, annotation, and quality issues.",
        description=(
            "Analyze a dataset for integrity problems, suspicious annotations, "
            "statistical anomalies, duplicates, and potential split leakage."
        ),
    )
    inspect.add_argument(
        "path",
        type=Path,
        help="Path to the dataset root directory.",
    )
    inspect.add_argument(
        "-f",
        "--format",
        dest="format",
        choices=available_formats(),
        default=None,
        help="Dataset format. Auto-detected when omitted.",
    )
    inspect.add_argument(
        "--no-images",
        dest="check_images",
        action="store_false",
        help="Skip checks that read image bytes (faster; skips corrupt-image detection).",
    )
    inspect.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if any WARNING is found (default: only ERRORs affect exit code).",
    )
    inspect.set_defaults(func=_cmd_inspect)

    return parser


def _cmd_inspect(args: argparse.Namespace) -> int:
    """Handle ``cvflow inspect <path>``.

    Loads the dataset, runs the analysis engine, prints a health report, and
    chooses an exit code based on the findings.
    """
    target: Path = args.path
    if not target.exists():
        print(f"{_PROG}: error: path does not exist: {target}", file=sys.stderr)
        return EXIT_TARGET_NOT_FOUND

    try:
        dataset = load_dataset(target, fmt=args.format)
    except DatasetError as exc:
        print(f"{_PROG}: error: {exc}", file=sys.stderr)
        return EXIT_LOAD_ERROR

    config = CheckConfig(check_images=args.check_images)
    engine = AnalysisEngine(default_checks(config))
    issues = engine.run(dataset)

    print(render_report(dataset, issues))

    has_error = any(i.severity is Severity.ERROR for i in issues)
    has_warning = any(i.severity is Severity.WARNING for i in issues)
    if has_error or (args.strict and has_warning):
        return EXIT_ISSUES_FOUND
    return EXIT_OK


def main(argv: Sequence[str] | None = None) -> int:
    """Program entry point.

    Args:
        argv: Argument vector excluding the program name. Defaults to
            ``sys.argv[1:]`` when ``None``.

    Returns:
        A process exit code.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    if getattr(args, "command", None) is None:
        parser.print_help()
        return EXIT_USAGE

    func = args.func  # set by each subcommand via set_defaults
    result = func(args)
    return int(result)


if __name__ == "__main__":  # pragma: no cover - exercised via the console script
    raise SystemExit(main())

"""CVFlow command-line entry point.

The ``inspect`` command loads a dataset, runs the analysis engine, and reports
the findings — as a prioritized text report by default, or as the browser
dashboard with ``--serve`` / ``--html``. Built on the standard-library
:mod:`argparse` to keep dependencies minimal; the CLI owns no analysis or
rendering logic of its own, only the wiring and the exit code.
"""

from __future__ import annotations

import argparse
import contextlib
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from cvflow import __version__
from cvflow.analysis import AnalysisEngine, CheckConfig, compute_statistics, default_checks
from cvflow.design import DEFAULT_HOST, Editor, render_dashboard, serve_dashboard
from cvflow.design.payload import TASK_LABELS
from cvflow.exceptions import DatasetError
from cvflow.loaders import available_formats, load_dataset
from cvflow.model import Dataset, Issue, Severity
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
            "CVFlow: ESLint / DevTools for computer-vision datasets. "
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
    inspect.add_argument(
        "--no-stats",
        dest="no_stats",
        action="store_true",
        help="Skip the dataset statistics section of the report.",
    )

    dashboard = inspect.add_argument_group("dashboard")
    dashboard.add_argument(
        "--serve",
        action="store_true",
        help="Open the findings in a browser dashboard instead of printing a text report.",
    )
    dashboard.add_argument(
        "--port",
        type=int,
        default=None,
        metavar="N",
        help="Port for --serve (default: the first free port from 8000).",
    )
    dashboard.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=f"Interface for --serve (default: {DEFAULT_HOST}).",
    )
    dashboard.add_argument(
        "--no-browser",
        dest="open_browser",
        action="store_false",
        help="With --serve, print the URL instead of opening a browser.",
    )
    dashboard.add_argument(
        "--html",
        type=Path,
        default=None,
        metavar="FILE",
        help="Write the dashboard to a self-contained HTML file (no server needed).",
    )
    inspect.set_defaults(func=_cmd_inspect)

    return parser


def _headline(dataset: Dataset, issues: list[Issue]) -> list[str]:
    """The short summary printed in place of the report when serving the UI.

    Two lines: what the dataset is, and what was found. The dashboard carries
    the detail, so the terminal says just enough to know it was read correctly.
    """
    counts = Counter(issue.severity for issue in issues)
    task = TASK_LABELS.get(dataset.task, dataset.task).lower()
    splits = ", ".join(dataset.splits) if dataset.splits else "no splits"
    return [
        f"{dataset.name}: {dataset.num_images:,} images, "
        f"{dataset.num_annotations:,} annotations, {dataset.num_classes:,} classes "
        f"({dataset.format.upper()} {task}, {splits}).",
        f"{len(issues):,} findings: "
        f"{counts.get(Severity.ERROR, 0):,} errors, "
        f"{counts.get(Severity.WARNING, 0):,} warnings, "
        f"{counts.get(Severity.INFO, 0):,} info.",
    ]


def _working_note(dataset: Dataset, check_images: bool) -> str:
    """Tell the user what is about to happen, and roughly how long it takes.

    Corrupt-image, duplicate and leakage detection read and hash every image,
    which on a real dataset is minutes, not seconds. Without a word first, a
    silent terminal looks like a hang.

    Written to stderr so piping the report to a file keeps it out.
    """
    images = f"{dataset.num_images:,} images"
    if not check_images:
        return f"Analyzing {images} from the labels only (--no-images). This is quick."
    return (
        f"Analyzing {images}: reading pixels for corrupt-image, duplicate and "
        "leakage checks. Generating these insights usually takes 1-5 minutes; "
        "pass --no-images to skip the pixel work."
    )


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
    print(_working_note(dataset, args.check_images), file=sys.stderr, flush=True)
    issues = engine.run(dataset)
    stats = None if args.no_stats else compute_statistics(dataset)

    if args.serve or args.html is not None:
        html = render_dashboard(dataset, issues, stats=stats, version=__version__)
        if args.html is not None:
            args.html.parent.mkdir(parents=True, exist_ok=True)
            args.html.write_text(html, encoding="utf-8")
            print(f"Dashboard written to {args.html}")
        if args.serve:
            for line in _headline(dataset, issues):
                print(line, flush=True)
            serve_dashboard(
                html,
                host=args.host,
                port=args.port,
                open_browser=args.open_browser,
                editor=Editor(dataset),
            )
    else:
        print(render_report(dataset, issues, stats=stats))

    has_error = any(i.severity is Severity.ERROR for i in issues)
    has_warning = any(i.severity is Severity.WARNING for i in issues)
    if has_error or (args.strict and has_warning):
        return EXIT_ISSUES_FOUND
    return EXIT_OK


def _use_utf8_output() -> None:
    """Make the report survive a redirect on Windows.

    A console defaults to the system code page (cp1252 here) when stdout is a
    pipe or a file, and the report's box-drawing rules are not encodable in it —
    ``cvflow inspect > report.txt`` would die with a UnicodeEncodeError. Switch
    our own streams to UTF-8, and degrade rather than crash if that fails.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:  # pragma: no cover - non-standard stream
            continue
        # Already closed or detached streams are not worth failing over.
        with contextlib.suppress(ValueError, OSError):
            reconfigure(encoding="utf-8", errors="replace")


def main(argv: Sequence[str] | None = None) -> int:
    """Program entry point.

    Args:
        argv: Argument vector excluding the program name. Defaults to
            ``sys.argv[1:]`` when ``None``.

    Returns:
        A process exit code.
    """
    _use_utf8_output()
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

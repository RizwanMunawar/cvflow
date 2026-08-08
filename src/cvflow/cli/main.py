"""CVFlow command-line entry point.

The foundation ships the CLI skeleton only: argument parsing, ``--version``,
``--help``, and an ``inspect`` command that validates its target and prints a
placeholder. The actual dataset analysis is wired in by later batches; keeping
the surface stable now means those batches only add behavior, not plumbing.

Built on the standard-library :mod:`argparse` to keep the foundation
dependency-free. Richer terminal output is introduced alongside the reporting
work that needs it.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from cvflow import __version__
from cvflow.exceptions import DatasetError
from cvflow.loaders import available_formats, load_dataset
from cvflow.model import Dataset

_PROG = "cvflow"

# Exit codes. These are part of the CLI contract that CI and scripts rely on,
# so they are defined once here and reused.
EXIT_OK = 0
EXIT_USAGE = 2
EXIT_TARGET_NOT_FOUND = 3
EXIT_LOAD_ERROR = 4


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
    inspect.set_defaults(func=_cmd_inspect)

    return parser


def _cmd_inspect(args: argparse.Namespace) -> int:
    """Handle ``cvflow inspect <path>``.

    Loads the dataset and prints a concise load summary. Full statistics,
    integrity checks, and quality analysis are wired in by later batches
    (M3+); for now this proves the loaders work end to end.
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

    _print_load_summary(dataset)
    return EXIT_OK


def _print_load_summary(dataset: Dataset) -> None:
    """Print a short, human-friendly summary of a freshly loaded dataset."""
    splits = dataset.splits
    splits_text = ", ".join(splits) if splits else "—"

    print(f"CVFlow {__version__}")
    print(f"Loaded {dataset.format.upper()} dataset: {dataset.name}")
    print(f"Root: {dataset.root}")
    print("─" * 40)
    print(f"{'Images':<14}{dataset.num_images:>10,}")
    print(f"{'Annotations':<14}{dataset.num_annotations:>10,}")
    print(f"{'Classes':<14}{dataset.num_classes:>10,}")
    print(f"{'Splits':<14}{splits_text:>10}")
    print()
    print("Analysis (integrity, annotations, statistics, duplicates, leakage)")
    print("is coming in the next batches. Track progress:")
    print("https://github.com/RizwanMunawar/cvflow")


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

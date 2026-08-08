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

_PROG = "cvflow"

# Exit codes. These are part of the CLI contract that CI and scripts rely on,
# so they are defined once here and reused.
EXIT_OK = 0
EXIT_USAGE = 2
EXIT_TARGET_NOT_FOUND = 3


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
    inspect.set_defaults(func=_cmd_inspect)

    return parser


def _cmd_inspect(args: argparse.Namespace) -> int:
    """Handle ``cvflow inspect <path>``.

    In the foundation this validates the target path and prints a placeholder.
    The analysis engine is connected in later batches (M2+).
    """
    target: Path = args.path
    if not target.exists():
        print(f"{_PROG}: error: path does not exist: {target}", file=sys.stderr)
        return EXIT_TARGET_NOT_FOUND

    print(f"CVFlow {__version__}")
    print(f"Target: {target.resolve()}")
    print()
    print("Dataset analysis is not implemented yet in this build.")
    print("Coming next: dataset loaders (YOLO, COCO) and the analysis engine.")
    print("Track progress: https://github.com/RizwanMunawar/cvflow")
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

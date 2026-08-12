# Contributing to CVFlow

Thanks for your interest in improving CVFlow! This guide covers how to get set
up and the conventions we follow.

## Development setup

CVFlow targets Python 3.9+ and has no runtime dependencies in the foundation.

```bash
git clone https://github.com/RizwanMunawar/cvflow
cd cvflow
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Before you push

All of the following must pass — CI runs the same checks:

```bash
ruff check .           # lint
ruff format --check .  # formatting
mypy                   # strict type-checking
pytest                 # tests
```

`ruff format .` auto-fixes formatting.

## Project layout

```
src/cvflow/
  model/      normalized, format-agnostic domain model (Issue, Severity, …)
  loaders/    dataset format loaders (YOLO, COCO, …)
  analysis/   the validation & analysis engine (rules)
  report/     turning findings into human-friendly / machine-readable output
  cli/        command-line interface
tests/        pytest suite mirroring the package structure
```

## Design principles

- **Deterministic first.** The MVP relies on validation, statistics, hashing,
  and lightweight CV techniques. AI/model-assisted checks are optional and come
  later — they must never be required.
- **Extensible core.** New formats, rules, algorithms, and outputs should slot
  in behind clear interfaces without rewriting the core.
- **Findings, not verdicts.** Every check emits an `Issue` with severity, a
  reason, a location, evidence, and a suggested action. Prefer language like
  "potential issue" / "worth reviewing" over declaring something definitively
  wrong.
- **Lean dependencies.** Add a dependency only when it clearly earns its place.

## Commits & PRs

- Keep PRs small and focused — one logical change per PR.
- Add or update tests for behavior changes.
- Reference the related Linear issue / GitHub issue where applicable.

## Reporting issues

Use GitHub Issues. For dataset-related bugs, a minimal reproducible dataset
layout (a few files) is enormously helpful.

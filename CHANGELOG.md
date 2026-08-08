# Changelog

All notable changes to CVFlow are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Dataset loaders (M2):
  - Normalized, format-agnostic dataset model (`BoundingBox`, `ImageItem`,
    `Dataset`) using canonical normalized `xyxy` box coordinates.
  - Pluggable loader abstraction (`DatasetLoader`) with a registry,
    auto-detection (`detect_format`), and a `load_dataset(path, fmt=None)`
    entry point.
  - **YOLO loader** — Ultralytics `data.yaml` plus the `images/`+`labels/`
    convention; class names from yaml / `classes.txt` / inferred.
  - **COCO loader** — single instances JSON or an `annotations/` directory of
    splits; absolute bboxes normalized via image dimensions.
  - `cvflow inspect <path>` now loads a dataset and prints a load summary
    (format, images, annotations, classes, splits), with an optional
    `--format` flag.
  - `pyyaml` added as the first runtime dependency (YOLO `data.yaml`).

## [0.1.0] — 2026-08-08

### Added

- Project foundation (M1):
  - `cvflow` Python package with a `src/` layout and a modular structure that
    anticipates the target architecture (`model`, `loaders`, `analysis`,
    `report`, `cli`).
  - CLI foundation (`cvflow`) built on the standard library: `--version`,
    `--help`, and a stubbed `cvflow inspect <path>` command.
  - Core domain primitives: `Severity` (ERROR / WARNING / INFO), `Issue`, and
    `Location`.
  - Packaging via `pyproject.toml` with a `cvflow` console entry point.
  - Tooling: ruff (lint + format), mypy (strict type-checking), pytest.
  - GitHub Actions CI: lint, type-check, and tests across Python 3.9–3.12.
  - Documentation: README, architecture notes, contributing guide, MIT license.

[Unreleased]: https://github.com/RizwanMunawar/cvflow/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/RizwanMunawar/cvflow/releases/tag/v0.1.0

# Changelog

All notable changes to CVFlow are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Dataset statistics:
  - `DatasetStatistics` / `Summary` model and `compute_statistics()` — class
    distribution, images-per-class, objects-per-image, box-area, aspect ratios,
    per-split counts, empty-image count (stdlib only, no numpy).
  - Statistical-anomaly checks: objects-per-image outliers (WARNING),
    rare classes (INFO), and class imbalance (INFO), with configurable,
    noise-resistant thresholds.
  - Report gains a "Dataset Statistics" section (objects/image, box size,
    aspect ratio, splits, class distribution with %).
  - `cvflow inspect` computes and shows statistics; `--no-stats` to skip.

- Annotation analysis:
  - Bounding-box geometry checks (`cvflow.analysis.annotations`): out-of-bounds
    boxes, negative coordinates, degenerate (zero/negative area) boxes,
    unusually tiny boxes, near-full-frame huge boxes, and duplicate/overlapping
    same-class boxes (IoU-based).
  - Tunable thresholds on `CheckConfig` (out-of-bounds epsilon, tiny side, huge
    area, duplicate IoU).
  - Report gains a "Findings by Type" section grouping issues by code with
    counts, sorted by severity then frequency.
  - Annotation checks wired into `cvflow inspect` via `default_checks()`.

- Integrity analysis:
  - Analysis engine (`AnalysisEngine`, `Check`, `CheckConfig`, `default_checks`)
    that runs checks over a dataset and returns severity-sorted `Issue`s.
  - Integrity checks: corrupt/unreadable images, broken image paths, invalid
    image dimensions, missing/empty annotations, invalid annotation files,
    invalid/unknown class ids, and duplicate filenames.
  - Human-friendly text report (`cvflow.report.render_report`): overview,
    health summary, prioritized "most important problems", and per-issue
    what/why/where/next details.
  - `cvflow inspect` now runs the engine and prints the health report, with
    `--no-images` (skip image-byte checks) and `--strict` (fail on warnings);
    exit code is non-zero when ERRORs (or, with `--strict`, WARNINGs) are found.
  - `pillow` added as a runtime dependency (corrupt-image detection).

- Dataset loaders:
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

- Project foundation:
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

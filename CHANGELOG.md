# Changelog

All notable changes to CVFlow are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.0.2] - 2026-08-11

First public release. CVFlow can load YOLO and COCO datasets and audit them for
integrity problems, annotation anomalies, statistical outliers, duplicate
images, and cross-split leakage, printing a single prioritized report.

### Added

- Project foundation:
  - `cvflow` Python package with a `src/` layout and a modular structure
    (`model`, `loaders`, `analysis`, `report`, `cli`).
  - CLI (`cvflow`) with `--version`, `--help`, and the `inspect` command.
  - Core domain primitives: `Severity` (ERROR / WARNING / INFO), `Issue`,
    `Location`.
  - Packaging via `pyproject.toml` with a `cvflow` console entry point.
  - Tooling: ruff (lint + format), mypy (strict), pytest.
  - GitHub Actions CI: lint, type-check, and tests across Python 3.9-3.12.
  - Documentation: README, architecture notes, contributing guide, MIT license.

- Dataset loaders:
  - Normalized, format-agnostic dataset model (`BoundingBox`, `ImageItem`,
    `Dataset`) using canonical normalized `xyxy` box coordinates.
  - Pluggable loader abstraction (`DatasetLoader`) with a registry,
    auto-detection (`detect_format`), and a `load_dataset(path, fmt=None)`
    entry point.
  - YOLO loader: Ultralytics `data.yaml` plus the `images/`+`labels/`
    convention; class names from yaml / `classes.txt` / inferred.
  - COCO loader: single instances JSON or an `annotations/` directory of
    splits; absolute bboxes normalized via image dimensions.
  - `pyyaml` added as the first runtime dependency (YOLO `data.yaml`).

- Integrity analysis:
  - Analysis engine (`AnalysisEngine`, `Check`, `CheckConfig`, `default_checks`)
    that runs checks over a dataset and returns severity-sorted `Issue`s.
  - Integrity checks: corrupt/unreadable images, broken image paths, invalid
    image dimensions, missing/empty annotations, invalid annotation files,
    invalid/unknown class ids, and duplicate filenames.
  - Human-friendly text report (`cvflow.report.render_report`): overview,
    health summary, prioritized problems, and per-issue what/why/where/next.
  - `--no-images` (skip image-byte checks) and `--strict` (fail on warnings);
    non-zero exit when ERRORs (or, with `--strict`, WARNINGs) are found.
  - `pillow` added as a runtime dependency (corrupt-image detection).

- Annotation analysis:
  - Bounding-box geometry checks (`cvflow.analysis.annotations`): out-of-bounds
    boxes, negative coordinates, degenerate (zero/negative area) boxes,
    unusually tiny boxes, near-full-frame huge boxes, and duplicate/overlapping
    same-class boxes (IoU-based).
  - Tunable thresholds on `CheckConfig` (out-of-bounds epsilon, tiny side, huge
    area, duplicate IoU).
  - Report gains a "Findings by Type" section grouping issues by code.

- Dataset statistics:
  - `DatasetStatistics` / `Summary` model and `compute_statistics()`: class
    distribution, images-per-class, objects-per-image, box-area, aspect ratios,
    per-split counts, empty-image count (stdlib only, no numpy).
  - Statistical-anomaly checks: objects-per-image outliers (WARNING), rare
    classes (INFO), and class imbalance (INFO), with noise-resistant thresholds.
  - Report gains a "Dataset Statistics" section; `--no-stats` to skip.

- Duplicate detection:
  - Imaging helpers: `file_hash` (SHA-256), `perceptual_hash` (dHash), and
    `hamming_distance` (Pillow only, no new dependency).
  - `ExactDuplicateCheck` groups byte-identical images; `NearDuplicateCheck`
    finds visually similar images with a similarity score.
  - Shared `resolve_image_path` in `cvflow.analysis.paths`, reused by integrity.

- Split-leakage detection:
  - `SplitLeakageCheck` (`cvflow.analysis.leakage`) finds visually similar
    images across dataset splits (train, val, test) via perceptual hashing,
    surfacing potential train/validation leakage.
  - Aggregated per split-pair: count of similar pairs, highest similarity, and
    an example pair; tunable `leakage_max_hamming`.

[Unreleased]: https://github.com/RizwanMunawar/cvflow/compare/v0.0.2...HEAD
[0.0.2]: https://github.com/RizwanMunawar/cvflow/releases/tag/v0.0.2

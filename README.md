<h1 align="center">🔍 CVFlow</h1>

<p align="center">
  <strong>ESLint / DevTools for computer-vision datasets.</strong><br>
  Point it at a dataset and find what's broken, duplicated, inconsistent, or suspicious —
  without inspecting thousands of images by hand.
</p>

<p align="center">
  <a href="https://github.com/RizwanMunawar/cvflow/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/RizwanMunawar/cvflow/actions/workflows/ci.yml/badge.svg"></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.9%2B-blue">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-green">
</p>

---

## What is CVFlow?

CVFlow is a developer-productivity and dataset-quality tool for computer-vision
engineers. It surfaces **suspicious, broken, duplicated, inconsistent, or
potentially problematic data** so you don't have to scroll through thousands of
images and annotation files looking for problems.

Think of it as **a linter for your dataset**: point it at a folder, get a
prioritized report of what to investigate first.

## Why should a CV developer care?

Datasets are where most model bugs actually live — corrupt images, boxes that
fall off the edge of the frame, mislabeled classes, near-duplicate frames from
the same video, or the same image leaking across your train and validation
splits. Finding these by eye is slow and error-prone. CVFlow does the tedious
scanning for you and tells you **what looks wrong, why, and where** — in minutes.

## How does it save time?

Instead of writing one-off scripts for every new dataset, run one command and
answer the questions that actually matter:

- Is anything **broken**? (corrupt images, missing/invalid annotations)
- Are my **annotations valid**? (out-of-bounds, zero-area, unknown classes)
- Are there **suspicious samples**? (statistical outliers)
- Do I have **duplicates**? (exact + near-duplicate images)
- Are my **splits leaking**? (train ↔ val similarity)
- Is my **distribution unusual**? (class imbalance, objects-per-image)
- **What should I investigate first**? (prioritized report)

## Quick start (under a minute)

```bash
# Install (from a source checkout)
pip install -e .

# Inspect a dataset
cvflow inspect ./dataset
```

```console
$ cvflow --help
usage: cvflow [-h] [-V] <command> ...

CVFlow — ESLint / DevTools for computer-vision datasets.

commands:
  inspect   Analyze a dataset and report integrity, annotation, and quality issues.
```

> **Status: early development (v0.1.0).** The CLI, packaging, domain model, CI,
> and **dataset loaders (YOLO + COCO)** are in place. Running `cvflow inspect`
> today loads your dataset and prints a summary; the analysis engine (integrity,
> annotations, statistics, duplicates, leakage) lands in the next batches — see
> the [roadmap](#roadmap).
>
> ```console
> $ cvflow inspect ./dataset
> CVFlow 0.1.0
> Loaded YOLO dataset: dataset
> Root: /path/to/dataset
> ────────────────────────────────────────
> Images                 3
> Annotations            4
> Classes                2
> Splits        train, val
> ```

## Product philosophy

> **Don't tell developers their dataset is wrong. Show them what looks
> suspicious, explain why, and let them decide.**

Every finding CVFlow reports carries: **what** was detected, **why** it was
flagged, **where**, a **severity** (`ERROR` / `WARNING` / `INFO`), the
**evidence** behind it, and a **suggested next action**. CVFlow uses careful
language ("potential issue", "worth reviewing") — it never claims an anomaly is
definitely an error.

## Roadmap

CVFlow is built in small, reviewable batches:

| Batch | Focus |
| ----- | ----- |
| **M1** | Project foundation — CLI, packaging, model, tests, CI ✅ |
| **M2** | Dataset loaders — YOLO & COCO → normalized model ✅ |
| **M3** | Integrity analysis — corrupt images, missing/invalid annotations |
| **M4** | Annotation analysis — bounding-box validation & anomalies |
| **M5** | Dataset statistics — distributions & outlier detection |
| **M6** | Duplicate detection — exact + perceptual hashing |
| **M7** | Split-leakage detection — cross-split similarity |
| **M8** | Visualization — inspect flagged samples |

## Architecture

```
Dataset
   ↓
Dataset Loaders            (cvflow.loaders)
   ↓
Normalized Dataset Model   (cvflow.model)
   ↓
Validation / Analysis      (cvflow.analysis)
   ├── Integrity Rules
   ├── Annotation Rules
   ├── Statistical Analysis
   ├── Duplicate Detection
   └── Split-Leakage Detection
   ↓
Issue Detection / Severity (cvflow.model.Issue / Severity)
   ↓
Report + Visualization     (cvflow.report)
```

New formats, rules, algorithms, and outputs can be added without rewriting the
core. See [`docs/architecture.md`](docs/architecture.md).

## Development

```bash
pip install -e ".[dev]"

ruff check .          # lint
ruff format .         # format
mypy                  # type-check
pytest                # tests
```

See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## License

[MIT](LICENSE) © Muhammad Rizwan Munawar

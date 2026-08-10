# CVFlow Architecture

CVFlow is designed so that new dataset formats, validation rules, detection
algorithms, output formats, and visualization features can be added **without
rewriting the core**. This document describes the intended shape of the system
and the boundaries that keep it extensible.

## Pipeline overview

```
Dataset (on disk)
   ↓
Dataset Loaders            cvflow.loaders
   ↓
Normalized Dataset Model   cvflow.model
   ↓
Validation / Analysis      cvflow.analysis
   ├── Integrity Rules
   ├── Annotation Rules
   ├── Statistical Analysis
   ├── Duplicate Detection
   └── Split-Leakage Detection
   ↓
Issues + Severity          cvflow.model.Issue / Severity
   ↓
Report + Visualization     cvflow.report
```

Data flows one direction. Each stage depends only on the stage before it via a
stable interface, never on the concrete implementations of other stages.

## Modules

### `cvflow.model` — normalized domain model
Format-agnostic types that everything else is expressed in. Introduced in the
foundation:

- **`Severity`** — `ERROR` / `WARNING` / `INFO`, ordered by seriousness.
- **`Issue`** — the unit of feedback: `code`, `severity`, `message`, `why`,
  `location`, `evidence`, `suggestion`.
- **`Location`** — where a finding was detected (path, split, annotation index).

The normalized dataset representation (images, annotations, splits, classes)
lands alongside the first loaders. Because the analysis engine only ever
sees the normalized model, loaders and rules evolve independently.

### `cvflow.loaders` — dataset loaders
Translate an on-disk dataset into the normalized model. Each format (YOLO, COCO,
…) is a self-contained loader. Adding a format means adding a loader — nothing
downstream changes.

### `cvflow.analysis` — validation & analysis engine
Hosts the checks. Each family of checks is independent and composable, and each
check emits `Issue` values rather than printing or deciding severity policy
elsewhere:

- **Integrity rules** — corrupt/unreadable images, missing/invalid annotation
  files, broken paths, invalid dimensions, duplicate filenames, invalid class
  IDs.
- **Annotation rules** — out-of-bounds, negative, zero/negative-area, tiny, or
  huge boxes; near-full-frame boxes; suspicious duplicates/overlaps; unknown
  classes.
- **Statistical analysis** — class distribution, objects-per-image, image
  dimensions and aspect ratios, split distribution, and outlier detection.
- **Duplicate detection** — exact (file hash) and near-duplicate (perceptual
  hash) images.
- **Split-leakage detection** — visually similar images appearing across splits.

### `cvflow.model.Issue` / `Severity` — issue detection & severity
Findings are uniform, which is what lets reporting, sorting, prioritization, and
visualization stay independent of the rules that produced them.

### `cvflow.report` — reporting
Turns a collection of `Issue`s into human-friendly, prioritized output — and,
later, machine-readable formats (e.g. JSON). New output formats are added here
without touching analysis.

### `cvflow.cli` — command-line interface
The user-facing entry point. Parses arguments and orchestrates
load → analyze → report. Kept thin: it wires stages together and owns no
analysis logic itself.

## Design principles

1. **Deterministic first.** Validation, statistics, hashing, and lightweight CV
   techniques form the MVP. AI/model-assisted semantic checks are optional and
   additive — never required.
2. **One-directional data flow.** Loaders → model → analysis → issues → report.
3. **Findings, not verdicts.** Severity + reason + evidence + suggestion;
   cautious language by default.
4. **Stable interfaces at the seams.** The normalized model and the `Issue` type
   are the contracts that let each layer change independently.
5. **Lean dependencies.** Introduced only in the batch that needs them.

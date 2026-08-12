# CVFlow Architecture

CVFlow is built so that new dataset formats, checks, detection algorithms, and
output formats can be added **without rewriting the core**. This document
describes how the pieces fit together and the boundaries that keep them
independent.

## Pipeline overview

```
Dataset (on disk)
   │
   ▼
Loaders                cvflow.loaders          detect format, parse to the model
   │
   ▼
Normalized model       cvflow.model            format-agnostic Dataset/BoundingBox
   │
   ▼
Analysis engine        cvflow.analysis         runs a list of checks, sorts findings
   ├── integrity        cvflow.analysis.integrity
   ├── annotations      cvflow.analysis.annotations
   ├── statistics       cvflow.analysis.statistics
   ├── duplicates       cvflow.analysis.duplicates
   └── leakage          cvflow.analysis.leakage
   │
   ▼
Issues + Severity      cvflow.model.Issue      uniform findings
   │
   ├──▶ Report          cvflow.report           human-friendly, prioritized text
   │
   └──▶ Design          cvflow.design           single-page browser dashboard
```

Data flows one direction. Each stage depends only on the stage before it through
a stable interface, never on another stage's internals.

## Modules

### `cvflow.model`: normalized domain model
The format-agnostic vocabulary everything else speaks in:

- **`Severity`**: `ERROR` / `WARNING` / `INFO`, ordered by seriousness.
- **`Issue`**: the unit of feedback: `code`, `severity`, `message`, `why`,
  `location`, `evidence`, `suggestion`.
- **`Location`**: where a finding was detected (path, split, annotation index).
- **`BoundingBox`**: a detection annotation in canonical **normalized `xyxy`**
  coordinates, with `from_yolo` / `from_coco` constructors and geometry helpers.
- **`ImageItem`** / **`Dataset`**: an image (path, split, dims, boxes) and the
  collection of them (format, root, class-name map, split/count helpers).
- **`DatasetStatistics`** / **`Summary`**: computed descriptive statistics
  (kept here, in the model, so the reporter never has to import `analysis`).

Because the analysis engine only ever sees this model, loaders and checks evolve
independently of one another.

### `cvflow.loaders`: dataset loaders
Translate an on-disk dataset into the normalized model. `DatasetLoader` is the
base interface (`detect()` / `load()`); a small **registry** exposes
`load_dataset(path, fmt=None)` with auto-detection and a clear
`UnsupportedFormatError`. `YoloLoader` and `CocoLoader` ship today. Adding a
format means adding a loader and registering it; nothing downstream changes.

Loaders are deliberately **lenient**: they represent whatever is on disk
(including out-of-range or malformed values) and leave judgment to the analysis
engine.

They also record the **task** they read: `detect`, `segment` or `obb`. One YOLO
text format serves all three, told apart by how many numbers follow the class id;
polygons and oriented boxes are reduced to their axis-aligned extent so every
check works on one geometry, while `Dataset.task` remembers what they came from.
That matters on the way back out: the editor refuses to rewrite anything but
plain detection labels.

### `cvflow.analysis`: the analysis engine and checks
- **`Check`**: the base class; `run(dataset) -> Iterable[Issue]`.
- **`AnalysisEngine`**: runs a list of checks and returns findings sorted
  most-severe-first.
- **`CheckConfig`**: one small options object (image-byte toggle plus tunable
  thresholds for box geometry, statistics, duplicates, and leakage). Checks read
  only the fields they care about, so new options don't ripple outward.
- **`default_checks(config)`**: assembles the full check set for `cvflow inspect`.

The check families, each self-contained and emitting `Issue`s (never printing or
setting global policy):

- **integrity**: corrupt/unreadable images, broken paths, invalid dimensions,
  missing/empty annotations, invalid annotation files, invalid class IDs,
  duplicate filenames.
- **annotations**: out-of-bounds, negative, zero/negative-area, tiny, huge, and
  duplicate/overlapping boxes.
- **statistics**: `compute_statistics()` for descriptive aggregates, plus
  anomaly checks (objects-per-image outliers, rare classes, class imbalance).
- **duplicates**: exact (file hash) and near-duplicate (perceptual hash) images.
- **leakage**: visually similar images appearing across splits.

### `cvflow.imaging`: image helpers
A thin, import-guarded wrapper over Pillow: readability/`verify`, size,
streamed SHA-256 (`file_hash`), perceptual dHash (`perceptual_hash`), and
`hamming_distance`. Isolating Pillow here keeps the rest of the codebase free of
a hard image dependency and gives duplicate/leakage detection a single source of
truth for hashing.

### `cvflow.analysis.paths`: image resolution
`resolve_image_path()` locates the actual image file for an `ImageItem` across
the layouts different formats use (absolute YOLO paths, bare COCO file names).
Shared by every check that reads pixels, so path handling lives in one place.

### `cvflow.report`: reporting
`render_report()` turns a list of `Issue`s (plus optional `DatasetStatistics`)
into a prioritized text report: overview, statistics, health summary,
most-important problems, findings-by-type, and per-issue detail. Reporting is
separate from analysis so new output formats (e.g. JSON) can be added without
touching the checks.

### `cvflow.design`: the visual layer
Everything the user sees in a browser. It is a **sibling** of `cvflow.report`,
not a layer above it: both consume `Issue`s and neither knows about the other.

- **`payload.build_payload()`**: the data contract. Turns a `Dataset`, its
  findings, and its statistics into one plain JSON-serializable dict, with every
  aggregate precomputed in Python — class ranking and cumulative coverage,
  objects/size/shape histograms, the box-center heatmap, per-code counts, and
  the images carrying the most findings. The page never reasons about the
  dataset itself; adding a chart usually means adding one function here.
- **`assets/`**: `dashboard.html`, `dashboard.css`, `dashboard.js` — the UI as
  editable design artifacts. No framework, no build step, no external requests.
  The page is a tabbed view (Overview / Classes / Geometry / Findings); every
  tab is rendered once at load and shown or hidden, so switching costs nothing
  and no chart has to re-measure itself.
- **`assets/vendor/`**: Chart.js and the Geist fonts, inlined into the page at
  render time. Vendoring them keeps `pip install cvflow` the only install step —
  no Node toolchain, no CDN, and the page still renders offline. Versions and
  licenses are listed in `assets/vendor/README.md`.
- **`editor.Editor`**: the write path. Resolves an image the browser asks for,
  returns its bytes and boxes, and writes edited boxes back to the YOLO label
  file. Every path is confined to the dataset root, and only YOLO is written —
  COCO's shared JSON is other tooling's to own, so it stays read-only.
- **`dashboard.render_dashboard()`**: inlines the assets and the payload into a
  single self-contained HTML file (`--html`, or served in memory).
- **`server.serve_dashboard()`**: a loopback `http.server` that holds one page
  in memory. With an `Editor` attached it also answers four JSON/image endpoints
  under `/api/`; without one it serves the page and 404s everything else. There
  is no static root and no directory listing either way.

The boundary is one-directional like every other seam here: the design layer
reads the model and never writes to it, so the UI can be redesigned without
touching a single check.

### `cvflow.sample`: the demo dataset
Downloads and unpacks Ultralytics' `coco128` into a cache directory when
`cvflow inspect` is run with no path, so the tool is useful on the first run.
Standard library only, cached after the first fetch, and every archive member is
resolved and checked before extraction so a crafted zip cannot write outside the
cache. Nothing here runs unless the path is omitted.

### `cvflow.cli`: command-line interface
The user-facing entry point (`cvflow inspect`). Parses arguments, wires
load → analyze → report, and chooses the process exit code from the findings.
Kept thin; it owns no analysis logic of its own.

## Extending CVFlow

- **New format** → add a `DatasetLoader` and register it.
- **New check** → add a `Check` and include it in `default_checks()`; the engine,
  CLI, and reporter pick it up automatically.
- **New threshold** → add a field to `CheckConfig`.
- **New output** → add a renderer in `cvflow.report`.
- **New UI** → edit the assets in `cvflow.design`; add a field to the payload
  only if the page needs data it doesn't already have.

None of these require changes outside their own module.

## Design principles

1. **Deterministic first.** Validation, statistics, hashing, and lightweight CV
   techniques form the core. AI/model-assisted checks would be additive and
   optional, never required.
2. **One-directional data flow.** Loaders → model → analysis → issues → report.
3. **Findings, not verdicts.** Every issue carries severity, reason, evidence,
   and a suggestion; cautious language by default.
4. **Stable interfaces at the seams.** The normalized model and the `Issue` type
   are the contracts that let each layer change independently.
5. **Lean dependencies.** Only two runtime dependencies (`pyyaml`, `pillow`),
   each added when a feature genuinely needed it. The dashboard adds none: it is
   standard-library rendering plus static assets.

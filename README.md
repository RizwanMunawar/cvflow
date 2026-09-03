<h1 align="center">🔍 CVFlow</h1>

<p align="center">
  <strong>A linter for computer-vision datasets.</strong><br>
  Point it at a folder of images and labels. It tells you what's broken,
  duplicated, mislabeled, or suspicious, before it wastes a training run.
</p>

<p align="center">
  <a href="https://github.com/RizwanMunawar/cvflow/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/RizwanMunawar/cvflow/actions/workflows/ci.yml/badge.svg"></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.9%2B-blue">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-green">
</p>
<p align="center">
  <a href="https://rizwanai.com">
    <img src="https://img.shields.io/badge/🌐%20rizwanai.com-purple?" alt="Portfolio">
  </a>
  <a href="https://github.com/RizwanMunawar">
    <img src="https://img.shields.io/badge/%20Projects%20%26%20Open%20Source-yellow?&logo=github&logoColor=white" alt="GitHub">
  </a>
  <a href="https://x.com/muhammdrizwanmr">
    <img src="https://img.shields.io/badge/Follow%20My%20Work-black?&logo=x&logoColor=white" alt="X">
  </a>
  <a href="https://www.linkedin.com/in/muhammadrizwanmunawar/">
    <img src="https://img.shields.io/badge/LinkedIn-Connect%20%26%20Collaborate-dodgerblue?&logo=linkedin&logoColor=white" alt="LinkedIn">
  </a>
</p>

https://github.com/user-attachments/assets/8bd483fe-c18a-4cfb-b209-8ba409327506

## Contents

**Getting started**
&nbsp;·&nbsp; [Quickstart](#quickstart)
&nbsp;·&nbsp; [Installation](#installation)
&nbsp;·&nbsp; [Your first run](#your-first-run)
&nbsp;·&nbsp; [Dataset layout](#how-your-dataset-should-be-laid-out)

**Using it**
&nbsp;·&nbsp; [The terminal report](#the-terminal-report)
&nbsp;·&nbsp; [The dashboard](#the-dashboard)
&nbsp;·&nbsp; [Fixing boxes in the browser](#fixing-boxes-without-leaving-the-page)
&nbsp;·&nbsp; [Command reference](#command-reference)
&nbsp;·&nbsp; [Common recipes](#common-recipes)

**Reference**
&nbsp;·&nbsp; [What it checks](#what-it-checks)
&nbsp;·&nbsp; [Every finding, by code](#every-finding-by-code)
&nbsp;·&nbsp; [In CI](#in-ci)
&nbsp;·&nbsp; [From Python](#from-python)
&nbsp;·&nbsp; [Troubleshooting](#troubleshooting)

**Contributing**
&nbsp;·&nbsp; [Testing & development](#testing--development)
&nbsp;·&nbsp; [How it fits together](#how-it-fits-together)
&nbsp;·&nbsp; [Design philosophy](#design-philosophy)

---

## Quickstart

Three commands. No config, no account, no setup.

```bash
pip install cvflow                     # 1. install
cvflow inspect                         # 2. no dataset? it fetches coco128 and checks that
cvflow inspect ./dataset --serve       # 3. or point it at yours and open the dashboard
```

That's the whole tool. `./dataset` is any folder holding a YOLO or COCO dataset;
CVFlow works out which one it is, and whether it holds boxes, polygons or
oriented boxes.

### Never used a terminal tool like this?

<details>
<summary><strong>Step-by-step, from nothing</strong></summary>

1. **Check you have Python 3.9 or newer.** In a terminal (Command Prompt on
   Windows, Terminal on macOS/Linux):

   ```bash
   python --version
   ```

   No Python? Install it from [python.org/downloads](https://www.python.org/downloads/).

2. **Install CVFlow:**

   ```bash
   pip install cvflow
   ```

3. **Try it.** With no dataset of your own, just run it: CVFlow downloads and
   unzips the `coco128` sample for you.

   ```bash
   cvflow inspect --serve
   ```

   Already have a dataset? Point at its folder instead:
   `cvflow inspect ./my-dataset --serve`

4. Your browser opens `http://localhost:8000` with the dashboard. Press
   `Ctrl+C` in the terminal when you're finished.

**`cvflow: command not found`?** Use `python -m cvflow` instead of `cvflow`.
Same tool, works even when your `PATH` isn't set up:

```bash
python -m cvflow inspect ./dataset --serve
```

</details>

## Installation

CVFlow needs **Python 3.9 or newer** and pulls in two runtime dependencies
(`pyyaml` and `pillow`).

```bash
pip install cvflow
cvflow --version
```

If your shell reports `cvflow: command not found`, the console script isn't on
your `PATH`. Use the module form instead — it's the same program:

```bash
python -m cvflow inspect ./dataset
```

To work on CVFlow itself, install it from a checkout with the dev extras. See
[Testing & development](#testing--development).

```bash
git clone https://github.com/RizwanMunawar/cvflow
cd cvflow
pip install -e ".[dev]"
```

## Your first run

Run `inspect` with no path and CVFlow downloads Ultralytics' `coco128` sample
(about 7 MB), unpacks it into a cache directory, and inspects that — so you can
see exactly what the tool does before arranging any data of your own.

```bash
cvflow inspect
```

The sample is fetched once and reused on every later run. Set `CVFLOW_CACHE` to
choose where it lands; otherwise CVFlow uses the platform cache home —
`%LOCALAPPDATA%\cvflow\cache` on Windows, and `$XDG_CACHE_HOME/cvflow` (falling
back to `~/.cache/cvflow`) everywhere else.

```bash
CVFLOW_CACHE=/data/cvflow-cache cvflow inspect
```

Nothing is downloaded when you pass a path of your own:

```bash
cvflow inspect ./dataset
```

Two rules of thumb are worth internalizing before you point it at real data:

- **Structure and annotation checks run from the labels alone.** They work even
  if the image files live somewhere else.
- **Corrupt-image, duplicate, and leakage checks need the pixels.** Point CVFlow
  at the folder that contains both the labels and the images. When the images
  can't be found, CVFlow says the image checks were skipped rather than
  inventing findings.

Reading and hashing every image takes minutes on a real dataset, so CVFlow
prints a note to stderr before it starts. Pass `--no-images` to skip the pixel
work entirely when you only want a fast structural pass.

## How your dataset should be laid out

CVFlow reads the two most common detection formats. The closer your folder is to
one of the layouts below, the more it can audit. In particular it needs to find
the **actual image files** on disk to check for corrupt images, duplicates, and
split leakage.

### YOLO

An Ultralytics-style `data.yaml` next to mirrored `images/` and `labels/` folders:

```text
dataset/
├── data.yaml
├── images/
│   ├── train/
│   │   ├── frame_0001.jpg
│   │   └── frame_0002.jpg
│   └── val/
│       └── frame_9001.jpg
└── labels/
    ├── train/
    │   ├── frame_0001.txt      # matches images/train/frame_0001.jpg
    │   └── frame_0002.txt
    └── val/
        └── frame_9001.txt
```

`data.yaml` names the classes and points at each split:

```yaml
path: .                 # optional; base for the paths below (relative to this file)
train: images/train
val: images/val
# test: images/test     # optional

names:                  # a list works too: [person, helmet]
  0: person
  1: helmet
```

A label file holds **one box per line** in normalized YOLO format: class id, then
box center and size, each as a fraction of the image (0–1):

```text
# class_id  cx     cy     w      h
0           0.512  0.437  0.104  0.216
1           0.300  0.300  0.050  0.080
```

A few things worth knowing:

- CVFlow finds a label by taking the image path and swapping `images/` →
  `labels/` and the extension → `.txt`. Keep that mirroring intact.
- An image with **no label file, or an empty one, is treated as a background
  image** (no objects); that's a WARNING to sanity-check, not an error.
- Supported image extensions: `.jpg .jpeg .png .bmp .webp .tif .tiff`.

**No `data.yaml`?** CVFlow falls back to a plain `images/` + `labels/` pair. It
picks up `train/`, `val/`, `test/` subfolders if present, otherwise treats
everything as one split. Class names come from `classes.txt` (one name per line)
if it exists, and are inferred from the label files otherwise.

### COCO

Annotation JSON(s) under `annotations/`, images under `images/`:

```text
dataset/
├── annotations/
│   ├── instances_train.json
│   └── instances_val.json
└── images/
    ├── train/
    │   └── 000000000001.jpg
    └── val/
        └── 000000009001.jpg
```

Each JSON is standard COCO: `images`, `annotations`, and `categories`:

```jsonc
{
  "images":     [{ "id": 1, "file_name": "000000000001.jpg", "width": 640, "height": 480 }],
  "annotations":[{ "id": 1, "image_id": 1, "category_id": 1, "bbox": [100, 120, 80, 160] }],
  "categories": [{ "id": 1, "name": "person" }]
}
```

Notes:

- COCO `bbox` is **absolute pixels** `[x, y, width, height]` with `(x, y)` at the
  top-left. CVFlow normalizes it using each image's `width`/`height`, so a YOLO
  box and a COCO box end up meaning the same thing.
- The **split** is inferred from the JSON filename: anything containing `train`,
  `val`, or `test`. A single JSON with no such hint loads as one unnamed split.
- To run the image-level checks (corrupt / duplicate / leakage), CVFlow needs the
  pixels. It looks for each `file_name` under the dataset root, then `images/`,
  then `images/<split>/` and `<split>/`. If it can't find them it still audits
  structure, annotations, and statistics, and tells you image checks were skipped
  rather than inventing false positives.

> **Rule of thumb:** structure and annotation checks run from the labels alone;
> corrupt-image, duplicate, and leakage checks need the image files reachable
> from the dataset root. Point CVFlow at the folder that contains both.

## The terminal report

The default output is a prioritized text report.

```bash
cvflow inspect ./dataset
```

```text
CVFlow Dataset Health
────────────────────────────────────────────────────
Format          YOLO
Images          12,482
Annotations     12,103
Classes         8
Splits          train, val

Health Summary
────────────────────────────────────────────────────
ERROR       17
WARNING    184
INFO         6

Most Important Problems
────────────────────────────────────────────────────
1. [ERROR]   17 images are unreadable or corrupt.
2. [ERROR]   21 bounding boxes extend outside the image boundaries.
3. [WARNING] 143 unusually small bounding boxes detected.
4. [WARNING] 127 highly similar image pairs between 'train' and 'val' (possible leakage).
5. [WARNING] Class 'helmet' represents only 0.4% of annotations.
```

It has six sections: the overview, dataset statistics (suppressed with
`--no-stats`), the health summary, the most important problems, a
findings-by-type breakdown, and per-issue detail for the top findings.

Severity is used honestly, and it's worth trusting:

| Severity | Means | Example |
|---|---|---|
| `ERROR` | Something is objectively broken. | A corrupt image, a box with negative area. |
| `WARNING` | Worth a look; CVFlow can't decide for you. | A tiny box, a near-duplicate pair, split leakage. |
| `INFO` | An observation, not a problem. | A rare class, a heavily imbalanced distribution. |

Statistical oddities and duplicates are never hard errors. They're candidates
for review, and they're phrased that way on purpose.

The progress note goes to stderr and the report to stdout, so
`cvflow inspect ./dataset > report.txt` captures just the report. It's written
as UTF-8 even when redirected, so that's safe on Windows consoles too.

The exit code is `0` when nothing's wrong and non-zero when there are errors, so
`cvflow inspect` drops straight into CI. Add `--strict` to fail on warnings too.
See [Exit codes](#exit-codes).

## The dashboard

The terminal report tells you what's wrong. The dashboard shows you, on one
page, with the images attached — and lets you fix boxes without leaving it.

```bash
cvflow inspect ./dataset --serve
```

```text
coco128: 128 images, 929 annotations, 71 classes (YOLO object detection, no splits).
98 findings: 0 errors, 49 warnings, 49 info.
Open http://localhost:8000 for the detail: every finding, its image, and the fix.
```

Your browser opens on the page; `Ctrl+C` in the terminal stops the server.

> **No extra install.** The charts are Chart.js and the type is Archivo, the
> Ultralytics brand face, both vendored inside the Python package and inlined
> into the page. No Node, no npm, no CDN: `pip install cvflow` is the whole
> setup and the page works offline.

One page, four tabs, everything hover- and keyboard-readable, light and dark:

| Tab | What it answers |
|---|---|
| **Overview** | How healthy is this dataset? What should I fix first, and how much accuracy is it worth? |
| **Classes** | Which classes dominate? How long is the tail? |
| **Geometry** | How big are the boxes, what shape, how many per image, and where in the frame do they sit? |
| **Findings** | Every finding, filterable by severity, check, split or free text. |

Every tab is rendered once at load and then shown or hidden, so switching costs
nothing.

### Serving it

| Option | Effect |
|---|---|
| `--serve` | Start the dashboard instead of printing the text report. |
| `--port N` | Bind this exact port. Omitted, CVFlow scans upward from 8000 for the first free one. |
| `--host HOST` | Interface to bind. Defaults to `127.0.0.1` — loopback only. |
| `--no-browser` | Print the URL instead of opening a browser. Use it over SSH, in a container, or in a tmux pane. |
| `--html FILE` | Write the same page to a self-contained file. Can be combined with `--serve`. |

```bash
# Loopback, opens your browser
cvflow inspect ./dataset --serve

# On a remote box: print the URL, bind a fixed port
cvflow inspect ./dataset --serve --no-browser --port 9000

# Reachable from your network (see the note below)
cvflow inspect ./dataset --serve --host 0.0.0.0 --port 9000
```

The server holds one page in memory. There is no static root and no directory
listing: with the editor attached it answers the page plus four `/api/`
endpoints; without one it serves the page and 404s everything else. Binding
`0.0.0.0` exposes both the page and, with it, read and write access to the labels
in your dataset folder to anyone who can reach that port — do that on a trusted
network only.

### Getting around

- **Hover any card** for a plain-English explanation of what it shows.
- **⤢** blows a chart up full screen; **↓** saves it as PNG or as the JSON
  behind it.
- **The rail button** collapses the sidebar.
- **Click any check or any image** — a bar in *Findings by type*, or one in
  *Images with the most findings* — to filter the findings view to it.
- **Findings** render as cards: severity, the headline, why it was flagged, a
  thumbnail of the image, and the suggested next step. Filter by severity,
  check, split or free text, and sort by any of them.
- **Arrow keys** move between tabs when a tab has focus; **Escape** closes the
  open overlay, tooltip, or editor.

**Accuracy headroom** (on the Overview tab) is a rough estimate of the accuracy
you could recover by fixing each class of problem, with its formula shown on
screen. Tick items off as you fix them and the remaining headroom updates. It's
labeled an estimate because it is one — treat it as a way to rank what to fix
first, not as a number to report.

### Fixing boxes without leaving the page

Click any finding that points at an image (or any bar in *Images with the most
findings*) and the photo opens with its boxes drawn on top. **The box the finding
is about is drawn in red**; every other class keeps its own colour. Down the right
side: what was flagged, why, the suggested next step, and one-click fixes
(*Clamp into frame*, *Delete this box*, *Reassign class*, *Add a box*). You can
also:

- drag a box to move it, drag its corner to resize,
- drag on empty canvas to draw a new one,
- change the class of the selected box, or delete it (`Delete` / `Backspace`),
- press `Escape` to close the editor,
- **Save labels** to write the corrections straight back to the label file.

Coordinates are clamped to the frame and reordered on the way in, so a box
dragged past an edge or drawn backwards still lands as valid data rather than as
a new finding. Saving also updates the in-memory dataset, so the dashboard and
any later save agree with what's now on disk.

#### What can be edited

Writing is allowed only for **YOLO detection** datasets served with `--serve`.
Everything else opens read-only, and the panel says which case you're in:

| Dataset | Editable? | Why |
|---|---|---|
| YOLO, `detect` | ✅ Yes | One small text file per image, so a change is contained and easy to review in git. |
| YOLO, `segment` or `obb` | ❌ Read-only | Those labels hold more than a box; rewriting a polygon as a rectangle would silently throw the mask away. |
| COCO, any task | ❌ Read-only | The annotation JSON is shared across the whole split and is other tooling's to own. |
| Any dataset via `--html` | ❌ Read-only | The static file has no backend to write with. |

A save writes one label file: one line per box, `class_id cx cy w h`, normalized
and mirrored from the image path. Images that had no label file get one created
at that mirrored path.

Every path the editor touches — reading an image, resolving a label file, writing
one — is resolved and confined to the dataset root. The editor writes in place and
keeps no backup, which is the point: your labels live in git, one file per image,
so a bad edit is a `git diff` away from being seen and a `git checkout` away from
being undone. If your dataset isn't under version control, make a copy before an
editing session.

### A file instead of a server

Prefer a file you can archive or attach to a PR? `--html` writes the same
self-contained page to disk, no server involved:

```bash
cvflow inspect ./dataset --html report.html
```

No server, no external requests, nothing to install to read it. It's the right
output for attaching to a PR, archiving with a dataset version, or uploading as
a CI artifact. The one thing the file can't do is edit — that needs the backend
`--serve` provides, so the annotation editor opens read-only.

## Command reference

```text
cvflow inspect [path] [options]

  path                       Dataset root. Omitted, CVFlow downloads and
                             inspects the coco128 sample.
  -f, --format {yolo,coco}   Force a format instead of auto-detecting.
      --no-images            Skip checks that read image bytes (much faster;
                             also skips corrupt/duplicate/leakage detection).
      --no-stats             Hide the dataset-statistics section.
      --strict               Exit non-zero on warnings, not just errors.

  dashboard:
      --serve                Open the findings in a browser dashboard instead
                             of printing a text report.
      --port N               Port for --serve (default: first free from 8000).
      --host HOST            Interface for --serve (default: 127.0.0.1).
      --no-browser           With --serve, print the URL instead of opening it.
      --html FILE            Write the dashboard to a self-contained HTML file.

  cvflow --version           Print the version.
  cvflow inspect --help      Show this list in your terminal.
```

Notes on individual options:

- **`--format`** only overrides detection. Reach for it when a folder looks like
  both formats, or when detection guesses wrong.
- **`--no-images`** turns off every check that opens an image file: corrupt
  images, exact and near duplicates, and split leakage. Structure, annotation
  geometry, and statistics still run.
- **`--strict`** changes the exit code only. It doesn't add checks or change the
  report.
- **`--serve` and `--html` can be combined.** The file is written first, then the
  server starts.
- **`--port`** is only a starting point when omitted: CVFlow scans upward from
  8000 for the first free port. Given explicitly, that exact port is bound.

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Clean — no errors (and no warnings under `--strict`). |
| `1` | Problems found: any `ERROR`, or any `WARNING` under `--strict`. |
| `2` | Bad usage — no subcommand given. |
| `3` | The path does not exist. |
| `4` | The dataset couldn't be loaded (unknown format, malformed, or the sample download failed). |

`INFO` findings never affect the exit code.

## Common recipes

```bash
# Kick the tyres with no dataset of your own
cvflow inspect --serve

# Fast structural check on a huge dataset (skips reading image bytes)
cvflow inspect ./dataset --no-images

# Gate a CI job on data quality
cvflow inspect ./dataset --strict

# Force the format when auto-detection can't tell
cvflow inspect ./dataset --format coco

# Just the findings, no statistics section, saved to a file
cvflow inspect ./dataset --no-stats > report.txt

# A self-contained page to attach to a PR
cvflow inspect ./dataset --html report.html

# Share the dashboard with a teammate on your network
cvflow inspect ./dataset --serve --host 0.0.0.0 --port 9000
```

## What it checks

Point CVFlow at a dataset and it answers the questions you'd otherwise check by
hand, one script at a time:

CVFlow reads **object detection**, **instance segmentation** and **oriented box
(OBB)** datasets. Polygons and oriented boxes are audited through their
axis-aligned extent, and the task is named in the sidebar and the terminal, so
you always know how your labels were read.

- **Is anything broken?** Corrupt/unreadable images, missing or invalid
  annotation files, broken paths, bad image dimensions, duplicate filenames.
- **Are the annotations sane?** Boxes outside the image, negative or zero-area
  boxes, absurdly tiny or full-frame boxes, duplicate overlapping boxes, class
  IDs that don't exist.
- **Is the distribution weird?** Class balance, objects per image, box sizes,
  aspect ratios, and images that are statistical outliers.
- **Do I have duplicates?** Exact copies (by hash) and near-duplicates (by
  perceptual hash, with a similarity score).
- **Are my splits leaking?** The same (or nearly the same) image in more than
  one split. This one bites hardest on datasets cut from video.

Every finding carries a severity, a plain-English reason, where it is, the
evidence behind it, and a suggested next step. CVFlow won't tell you your dataset
is *wrong*; it shows you what looks off and lets you make the call.

## Every finding, by code

Every finding carries a stable `code`. Checks run in six families and are
reported most-severe-first. Checks marked **needs pixels** open the image files,
so they're skipped by `--no-images` and when the images can't be found under the
dataset root.

### Integrity

Structural problems: files that are missing, unreadable, or internally
inconsistent.

| Code | Severity | Triggered when |
|---|---|---|
| `corrupt-image` | ERROR | The image file exists but can't be decoded. **Needs pixels.** |
| `broken-image-path` | ERROR | The annotations reference an image that isn't on disk. |
| `invalid-image-dimension` | ERROR | The recorded width or height is zero or negative. |
| `invalid-annotation-file` | ERROR | A YOLO label file has malformed lines (not `class_id cx cy w h` with numeric values). |
| `invalid-class-id` | ERROR / WARNING | A box uses a class id that isn't in the class map. `ERROR` when the id is negative, `WARNING` otherwise. Skipped entirely when the dataset defines no class names. |
| `duplicate-filename` | WARNING | The same image filename appears more than once — a common sign of a merge that overwrote samples. |
| `empty-image` | WARNING | An image has no annotations. Legitimate for background samples, so it's a prompt to confirm, not a failure. One finding per image up to a limit, then the tail is summarized in one further finding. |
| `images-not-found` | INFO | No image file could be located under the dataset root, so every pixel-reading check was skipped. Reported once, instead of flooding the report with false `broken-image-path` findings. |

### Annotations

Box geometry, on every task — polygons and oriented boxes are audited through
their axis-aligned extent.

| Code | Severity | Triggered when | Threshold |
|---|---|---|---|
| `box-out-of-bounds` | ERROR | A normalized coordinate falls outside `0–1`. | `out_of_bounds_eps` (`1e-3`) tolerance before it counts |
| `degenerate-box` | ERROR | Width or height is zero or negative. | — |
| `tiny-box` | WARNING | A side is below 1% of the image. Degenerate boxes are excluded; they're reported by their own check. | `tiny_box_side` (`0.01`) |
| `huge-box` | WARNING | The box covers more than 90% of the frame. | `huge_box_area` (`0.9`) |
| `duplicate-annotation` | WARNING | Two same-class boxes in one image overlap with IoU at or above the threshold. | `duplicate_iou` (`0.95`) |

### Shapes

Task-specific geometry. Each of these is a no-op unless the dataset's task
matches, so a detection dataset never sees them.

**Segmentation only:**

| Code | Severity | Triggered when | Threshold |
|---|---|---|---|
| `sparse-polygon` | ERROR | A polygon has fewer than three points, so it can't enclose an area. | — |
| `empty-mask` | ERROR | The polygon encloses zero area. | — |
| `rectangular-mask` | WARNING | The mask fills essentially all of its own bounding box — it's a rectangle wearing a polygon's clothes. | `rectangular_mask_fill` (`0.98`) |
| `sliver-mask` | WARNING | The mask fills very little of its own extent, which usually means a broken or collapsed contour. | `sliver_mask_fill` (`0.05`) |

**Oriented boxes (OBB) only:**

| Code | Severity | Triggered when | Threshold |
|---|---|---|---|
| `non-rectangular-obb` | WARNING | A corner deviates from square by more than the tolerance, so the four points aren't a rectangle. | `obb_corner_tolerance` (`5.0` degrees) |
| `unrotated-obb` | INFO | *Every* oriented box in the dataset is axis-aligned — the dataset is labeled as OBB but carries no rotation, so it may have been exported as plain boxes. Reported once for the dataset. | `obb_flat_tolerance` (`1.0` degrees) |

### Statistics

Distribution anomalies. All of these are candidates for review, never verdicts,
which is why none of them is an `ERROR`.

| Code | Severity | Triggered when | Threshold |
|---|---|---|---|
| `objects-per-image-outlier` | WARNING | An image holds far more objects than the dataset average — above `mean + sigma × std`, and above an absolute floor so small datasets don't produce noise. | `objects_outlier_sigma` (`3.0`), `objects_outlier_floor` (`10`) |
| `rare-class` | INFO | A class accounts for less than 1% of all annotations. | `rare_class_fraction` (`0.01`) |
| `class-imbalance` | INFO | The most-common class outnumbers the least-common by more than 100×. Reported once for the dataset. | `class_imbalance_ratio` (`100.0`) |

The same module also computes the descriptive statistics printed in the report
and charted in the dashboard: class counts, objects per image, box areas, and
aspect ratios. Those are suppressed with `--no-stats`, but the checks above still
run.

### Duplicates

Redundant samples. Both checks hash the image files, so both **need pixels**.

| Code | Severity | Triggered when | Threshold |
|---|---|---|---|
| `exact-duplicate` | WARNING | Two or more images share an identical SHA-256 — byte-for-byte copies. One finding per group, listing up to ten paths. | — |
| `near-duplicate` | WARNING | Two images' perceptual hashes (64-bit dHash) differ by at most 5 bits. A distance of 0 is skipped, since `exact-duplicate` already covers it. Reporting stops after 100 pairs so a heavily duplicated dataset can't flood the report. | `near_duplicate_max_hamming` (`5`), `max_reported_duplicate_pairs` (`100`) |

Near-duplicate detection is a pairwise comparison, which is the slow part of a
run on a large dataset. `--no-images` skips it.

### Leakage

| Code | Severity | Triggered when | Threshold |
|---|---|---|---|
| `split-leakage` | WARNING | Visually near-identical images appear in two different splits — their perceptual hashes differ by at most 5 bits. One finding per pair of splits, counting every match and naming the closest one. **Needs pixels.** | `leakage_max_hamming` (`5`) |

This check only runs when the dataset has at least two splits. It's the one that
bites hardest on datasets cut from video, where consecutive frames end up on both
sides of a train/val boundary and inflate your metrics.

### Tuning the thresholds

The CLI deliberately exposes only `--no-images`; every other threshold lives on
`CheckConfig` and is reachable from Python:

```python
from cvflow.analysis import AnalysisEngine, CheckConfig, default_checks
from cvflow.loaders import load_dataset

config = CheckConfig(
    tiny_box_side=0.005,  # your objects really are that small
    near_duplicate_max_hamming=2,  # only flag very close pairs
    rare_class_fraction=0.02,
)
issues = AnalysisEngine(default_checks(config)).run(load_dataset("./dataset"))
```

Every field, with its default, is documented inline on `CheckConfig` in
[`src/cvflow/analysis/engine.py`](src/cvflow/analysis/engine.py). Checks read only
the fields they care about, so adding one doesn't ripple outward.

## In CI

Because the exit code is meaningful, `cvflow inspect` drops straight into a
pipeline as a data-quality gate.

<details>
<summary><strong>Show the workflow steps</strong></summary>

<br>

```yaml
- name: Check dataset quality
  run: |
    pip install cvflow
    cvflow inspect ./dataset --strict
```

A few things make CI runs pleasanter:

- Use `--no-images` when the images aren't checked out, or when the run has to
  stay under a couple of minutes. You lose corrupt/duplicate/leakage detection.
- Use `--html report.html` and upload the file as a build artifact. It's
  self-contained — one HTML file, no server, no external requests — so it
  attaches to a PR or an artifact store as-is.

```yaml
- name: Dataset report
  run: cvflow inspect ./dataset --strict --html report.html
- uses: actions/upload-artifact@v4
  if: always()
  with:
    name: dataset-report
    path: report.html
```

</details>

## From Python

The CLI is thin wiring over a small public API, so you can run the same pipeline
yourself — to filter findings, feed them into another tool, or tune a threshold
the CLI doesn't expose.

<details>
<summary><strong>Show the Python API</strong></summary>

<br>

```python
from cvflow.analysis import AnalysisEngine, CheckConfig, compute_statistics, default_checks
from cvflow.loaders import load_dataset
from cvflow.model import Severity
from cvflow.report import render_report

dataset = load_dataset("./dataset")  # fmt="coco" to force a format
config = CheckConfig(check_images=True, tiny_box_side=0.005)
issues = AnalysisEngine(default_checks(config)).run(dataset)

errors = [issue for issue in issues if issue.severity is Severity.ERROR]
print(f"{len(errors)} errors out of {len(issues)} findings")

print(render_report(dataset, issues, stats=compute_statistics(dataset)))
```

`load_dataset` raises `cvflow.exceptions.DatasetError` (or its
`UnsupportedFormatError` subclass) when the path can't be read as a dataset.
Findings come back sorted most-severe-first, and every `Issue` carries a `code`,
`severity`, `message`, `why`, `location`, `evidence`, and `suggestion`. Nothing
in this API prints or exits; that's the CLI's job alone.

To run a subset of the check families rather than all of them, assemble the list
yourself — `integrity_checks`, `annotation_checks`, `shape_checks`,
`statistics_checks`, `duplicate_checks` and `leakage_checks` each return the
checks for one family:

```python
from cvflow.analysis import AnalysisEngine, CheckConfig, annotation_checks, integrity_checks

config = CheckConfig()
engine = AnalysisEngine([*integrity_checks(config), *annotation_checks(config)])
```

</details>

## Troubleshooting

**`cvflow: command not found`** — use `python -m cvflow` instead.

**`error: path does not exist`** (exit 3) — check the path; CVFlow doesn't
search for it.

**The format couldn't be detected** (exit 4) — the folder doesn't look like
either layout. Pass `-f yolo` or `-f coco` to force one, or move the labels and
images into the expected structure.

**Every image reports `broken-image-path`** — the labels reference images CVFlow
can't find from the dataset root. Point it at the parent folder that holds both,
or fix the paths in `data.yaml`.

**"No image files were found next to the annotations"** — an `INFO` finding, not
a failure. The structural and annotation checks still ran; only the pixel checks
were skipped.

**The run seems to hang** — it's hashing images. The stderr note says so before
it starts; `--no-images` skips that phase.

**The browser didn't open** — the URL is printed either way; open it by hand.
`--no-browser` makes that the intended behavior.

**"Address already in use"** — you passed `--port` for a port something else
holds. Drop `--port` to let CVFlow find a free one.

**A teammate can't reach the dashboard** — the default host is loopback. Re-run
with `--host 0.0.0.0`, and read [the warning](#serving-it) about what that
exposes.

**Save is greyed out in the editor** — the dataset isn't YOLO detection, or
you're looking at an `--html` file. See [What can be edited](#what-can-be-edited).

## Testing & development

```bash
git clone https://github.com/RizwanMunawar/cvflow
cd cvflow
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### Run the checks

All four must pass — CI runs exactly these:

```bash
ruff check .           # lint
ruff format --check .  # formatting  (ruff format .  auto-fixes)
mypy                   # strict type-checking
pytest                 # tests
```

Handy `pytest` variations while you work:

```bash
pytest -q                                  # quiet
pytest tests/test_annotations.py           # one file
pytest -k "leakage or duplicate"           # by name
pytest --cov=cvflow --cov-report=term-missing   # with coverage, as CI runs it
pytest -x -vv                              # stop at the first failure, verbose
```

The suite is pure-Python and fast — no fixtures to download and no GPU. Tests
mirror the package structure one file per module, and
[`tests/conftest.py`](tests/conftest.py) builds minimal-but-valid YOLO and COCO
datasets in a temp directory, so loader and check tests exercise real file
parsing without shipping binary fixtures.

CI runs lint and type-checking on Python 3.11, and the test suite on 3.9, 3.10,
3.11 and 3.12. See [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

### Try it end to end

Build a tiny broken dataset by hand and watch CVFlow catch it — the fastest way
to see the whole pipeline work after a change:

```bash
mkdir -p demo/images/train demo/labels/train

python -c "
from PIL import Image
Image.new('RGB', (640, 480), (90, 110, 140)).save('demo/images/train/frame_0001.jpg')
Image.new('RGB', (640, 480), (40, 60,  80)).save('demo/images/train/frame_0002.jpg')
"

cat > demo/data.yaml <<'YAML'
path: .
train: images/train

names:
  0: person
  1: helmet
YAML

# one good box, one that runs off the right edge, one that's absurdly tiny
printf '0 0.512 0.437 0.104 0.216\n1 0.980 0.500 0.200 0.100\n' > demo/labels/train/frame_0001.txt
printf '0 0.500 0.500 0.002 0.003\n'                            > demo/labels/train/frame_0002.txt

cvflow inspect ./demo
```

You should see one `ERROR` (`box-out-of-bounds`) and one `WARNING`
(`tiny-box`), and the process should exit `1`:

```text
Health Summary
────────────────────────────────────────────────────
ERROR        1
WARNING      1
INFO         0
```

```bash
echo $?          # 1  — errors were found
```

Then check the other two outputs against the same folder:

```bash
cvflow inspect ./demo --serve     # the dashboard, with the editor live
cvflow inspect ./demo --html report.html && open report.html   # the static page
```

Open a box in the dashboard, drag it back inside the frame, hit **Save labels**,
and re-run `cvflow inspect ./demo` — the `box-out-of-bounds` error should be
gone and the exit code back to `0`.

### Conventions

- Keep PRs small and focused — one logical change per PR.
- Add or update tests for behavior changes.
- Prefer language like "potential issue" / "worth reviewing" over declaring
  something definitively wrong — see [Design philosophy](#design-philosophy).
- Add a dependency only when it clearly earns its place.

More detail in [`CONTRIBUTING.md`](CONTRIBUTING.md). For dataset-related bug
reports, a minimal reproducible dataset layout (a few files) is enormously
helpful.

## How it fits together

```text
Dataset ─▶ Loaders ─▶ Normalized model ─▶ Analysis engine ─▶ Issues ─┬─▶ Report  (text)
                        (cvflow.model)      ├─ integrity             │
                                            ├─ annotations           └─▶ Design (dashboard)
                                            ├─ shapes
                                            ├─ statistics
                                            ├─ duplicates
                                            └─ leakage
```

Data flows one direction. Each stage depends only on the stage before it through
a stable interface, never on another stage's internals — so a new format, rule,
or output slots in without touching the rest.

```text
src/cvflow/
  model/      normalized, format-agnostic domain model (Issue, Severity, …)
  loaders/    dataset format loaders (YOLO, COCO)
  analysis/   the analysis engine and every check
  imaging.py  the only place Pillow is used: readability, hashing, dHash
  report/     findings → prioritized text report
  design/     findings → the browser dashboard and its editor
  sample.py   downloads coco128 when inspect is run with no path
  cli/        the command-line entry point
tests/        pytest suite mirroring the package structure
```

<details>
<summary><strong>Module-by-module detail</strong></summary>

### `cvflow.model`: normalized domain model

The format-agnostic vocabulary everything else speaks in:

- **`Severity`**: `ERROR` / `WARNING` / `INFO`, ordered by seriousness.
- **`Issue`**: the unit of feedback — `code`, `severity`, `message`, `why`,
  `location`, `evidence`, `suggestion`.
- **`Location`**: where a finding was detected (path, split, annotation index).
- **`BoundingBox`**: an annotation in canonical **normalized `xyxy`**
  coordinates, with `from_yolo` / `from_coco` constructors and geometry helpers.
- **`ImageItem`** / **`Dataset`**: an image (path, split, dims, boxes) and the
  collection of them (format, root, class-name map, split/count helpers).
- **`DatasetStatistics`** / **`Summary`**: computed descriptive statistics — kept
  in the model so the reporter never has to import `analysis`.

Because the analysis engine only ever sees this model, loaders and checks evolve
independently of one another.

### `cvflow.loaders`: dataset loaders

Translate an on-disk dataset into the normalized model. `DatasetLoader` is the
base interface (`detect()` / `load()`); a small registry exposes
`load_dataset(path, fmt=None)` with auto-detection and a clear
`UnsupportedFormatError`. `YoloLoader` and `CocoLoader` ship today.

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
- **`CheckConfig`**: one small options object (image-byte toggle plus the
  thresholds listed under [Every finding, by code](#every-finding-by-code)).
  Checks read only the fields they care about.
- **`default_checks(config)`**: assembles the full check set for `cvflow inspect`.

Each family — integrity, annotations, shapes, statistics, duplicates, leakage —
is self-contained and emits `Issue`s, never printing or setting global policy.

### `cvflow.imaging` and `cvflow.analysis.paths`

`imaging` is a thin, import-guarded wrapper over Pillow: readability/`verify`,
size, streamed SHA-256 (`file_hash`), perceptual dHash (`perceptual_hash`), and
`hamming_distance`. Isolating Pillow here keeps the rest of the codebase free of
a hard image dependency and gives duplicate/leakage detection one source of truth
for hashing.

`analysis.paths.resolve_image_path()` locates the actual image file for an
`ImageItem` across the layouts different formats use (absolute YOLO paths, bare
COCO file names). Shared by every check that reads pixels, so path handling lives
in one place.

### `cvflow.report`: reporting

`render_report()` turns a list of `Issue`s (plus optional `DatasetStatistics`)
into a prioritized text report: overview, statistics, health summary,
most-important problems, findings-by-type, and per-issue detail. Reporting is
separate from analysis so new output formats can be added without touching the
checks.

### `cvflow.design`: the visual layer

Everything the user sees in a browser. It's a **sibling** of `cvflow.report`, not
a layer above it: both consume `Issue`s and neither knows about the other.

- **`payload.build_payload()`**: the data contract. Turns a `Dataset`, its
  findings, and its statistics into one plain JSON-serializable dict, with every
  aggregate precomputed in Python — class ranking and cumulative coverage,
  objects/size/shape histograms, the box-center heatmap, per-code counts, and the
  images carrying the most findings. The page never reasons about the dataset
  itself; adding a chart usually means adding one function here.
- **`assets/`**: `dashboard.html`, `dashboard.css`, `dashboard.js` — the UI as
  editable design artifacts. No framework, no build step, no external requests.
- **`assets/vendor/`**: Chart.js and the Geist fonts, inlined into the page at
  render time. Versions and licenses in `assets/vendor/README.md`.
- **`editor.Editor`**: the write path. Resolves an image the browser asks for,
  returns its bytes and boxes, and writes edited boxes back to the YOLO label
  file. Every path is confined to the dataset root, and only YOLO detection is
  written.
- **`dashboard.render_dashboard()`**: inlines the assets and the payload into a
  single self-contained HTML file (`--html`, or served in memory).
- **`server.serve_dashboard()`**: a loopback `http.server` holding one page in
  memory. With an `Editor` attached it also answers four endpoints —
  `GET /api/editor` (is this dataset writable, and which classes?),
  `GET /api/image`, `GET /api/annotations`, `POST /api/annotations` — and without
  one it serves the page and 404s everything else.

### `cvflow.sample` and `cvflow.cli`

`sample` downloads and unpacks Ultralytics' `coco128` into a cache directory when
`cvflow inspect` is run with no path. Standard library only, cached after the
first fetch, and every archive member is resolved and checked before extraction
so a crafted zip can't write outside the cache. Nothing here runs unless the path
is omitted.

`cli` is the user-facing entry point. It parses arguments, wires
load → analyze → report, and chooses the process exit code from the findings. It
owns no analysis logic of its own.

</details>

### Extending CVFlow

- **New format** → add a `DatasetLoader` and register it.
- **New check** → add a `Check` and include it in `default_checks()`; the engine,
  CLI, and reporter pick it up automatically.
- **New threshold** → add a field to `CheckConfig`.
- **New output** → add a renderer in `cvflow.report`.
- **New UI** → edit the assets in `cvflow.design`; add a field to the payload only
  if the page needs data it doesn't already have.

None of these require changes outside their own module. Add tests alongside, and
run the four checks above before you push.

## Design philosophy

> Don't tell developers their dataset is wrong. Show them what looks suspicious,
> explain why, and let them decide.

That principle is baked into the tool. Severity is used honestly: `ERROR` means
something is objectively broken, `WARNING` means "worth a look", and `INFO` is an
observation. Statistical oddities and duplicates are never hard errors; they're
candidates for review, phrased that way on purpose. The dashboard's accuracy
estimate is labeled an estimate, with its formula on screen.

Four rules hold the codebase together:

1. **Deterministic first.** Validation, statistics, hashing, and lightweight CV
   techniques form the core. AI/model-assisted checks would be additive and
   optional, never required.
2. **One-directional data flow.** Loaders → model → analysis → issues → report.
3. **Findings, not verdicts.** Every issue carries severity, reason, evidence,
   and a suggestion; cautious language by default.
4. **Lean dependencies.** Two runtime dependencies (`pyyaml`, `pillow`), each
   added when a feature genuinely needed it. The dashboard adds none: it's
   standard-library rendering plus static assets.

## Roadmap

- ✅ **Project foundation**: CLI, packaging, model, tests, CI
- ✅ **Dataset loaders**: YOLO & COCO → one normalized model
- ✅ **Integrity analysis**: corrupt images, missing/invalid annotations
- ✅ **Annotation analysis**: bounding-box validation & anomalies
- ✅ **Dataset statistics**: distributions & outlier detection
- ✅ **Duplicate detection**: exact + perceptual hashing
- ✅ **Split-leakage detection**: cross-split similarity
- ✅ **Dashboard**: one browser page for the whole report
- ✅ **Visualization**: eyeball the flagged samples

## License

CVFlow is released under the [MIT License](LICENSE).

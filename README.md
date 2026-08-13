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

## Quickstart

Three commands. No config, no account, no setup.

```bash
pip install cvflow                     # 1. install
cvflow inspect                         # 2. no dataset? it fetches coco128 and checks that
cvflow inspect ./dataset --serve       # 3. or point it at yours and open the dashboard
```

Running `cvflow inspect` with no path downloads Ultralytics' `coco128` sample
(about 7 MB) into a cache directory and inspects it, so you can see exactly what
the tool does before arranging any data. It is fetched once and reused; set
`CVFLOW_CACHE` to choose where it lands.

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

## What you get

### The dashboard: `--serve`

```bash
cvflow inspect ./dataset --serve
# coco128: 128 images, 929 annotations, 71 classes (YOLO object detection, no splits).
# 98 findings: 0 errors, 49 warnings, 49 info.
# Open http://localhost:8000 for the detail: every finding, its image, and the fix.
```

One page, four tabs, everything hover- and keyboard-readable, light and dark:

| Tab | What it answers |
|---|---|
| **Overview** | How healthy is this dataset? What should I fix first, and how much accuracy is it worth? |
| **Classes** | Which classes dominate? How long is the tail? |
| **Geometry** | How big are the boxes, what shape, how many per image, and where in the frame do they sit? |
| **Findings** | Every finding, filterable by severity, check, or free text. |

> **No extra install.** The charts are Chart.js and the type is Archivo, the
> Ultralytics brand face, both vendored inside the Python package and inlined
> into the page. No Node, no npm, no CDN: `pip install cvflow` is the whole
> setup and the page works offline.

Handy bits: hover any card for a plain-English explanation of what it shows, use
**⤢** to blow it up full screen or **↓** to save it as PNG or JSON, collapse the
sidebar with the rail button, click any check or image to filter the findings to
it, and use the **Accuracy headroom** panel to estimate what fixing each problem
is worth. Tick items off as you go and the number updates.

Findings render as cards: severity, the headline, why it was flagged, a thumbnail
of the image, and the suggested next step. Filter by severity, check, split or
free text, and sort by any of them.

### Fix boxes without leaving the page

Click any finding that points at an image (or any bar in *Images with the most
findings*) and the photo opens with its boxes drawn on top. **The box the finding
is about is drawn in red**; every other class keeps its own colour. Down the right
side: what was flagged, why, the suggested next step, and one-click fixes
(*Clamp into frame*, *Delete this box*, *Reassign class*, *Add a box*). You can
also:

- drag a box to move it, drag its corner to resize,
- drag on empty canvas to draw a new one,
- change the class of the selected box, or delete it,
- **Save labels** to write the corrections straight back to the label file.

Editing needs `--serve` (the static `--html` file has no backend) and writes
**YOLO detection** labels only: one small text file per image, so a change is
contained and easy to review in git. COCO, segmentation and OBB datasets open
read-only, because rewriting a polygon as a box would silently throw the mask
away, and the panel says so. Everything is confined to your dataset folder: the
server serves that one page plus images from inside the dataset root, nothing else.

Prefer a file you can archive or attach to a PR? `--html` writes the same
self-contained page to disk, no server involved:

```bash
cvflow inspect ./dataset --html report.html
```

### The terminal report: the default

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

The exit code is `0` when nothing's wrong and non-zero when there are errors, so
`cvflow inspect` drops straight into CI. Add `--strict` to fail on warnings too.

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

Exit codes: `0` clean · `1` problems found (errors, or warnings under `--strict`)
· `2` bad usage · `3` path not found · `4` the dataset couldn't be loaded.

### Common recipes

```bash
# Kick the tyres with no dataset of your own
cvflow inspect --serve

# Fast structural check on a huge dataset (skips reading image bytes)
cvflow inspect ./dataset --no-images

# Gate a CI job on data quality
cvflow inspect ./dataset --strict

# Force the format when auto-detection can't tell
cvflow inspect ./dataset --format coco

# Share the dashboard with a teammate on your network
cvflow inspect ./dataset --serve --host 0.0.0.0 --port 9000
```

## Design philosophy

> Don't tell developers their dataset is wrong. Show them what looks suspicious,
> explain why, and let them decide.

That principle is baked into the tool. Severity is used honestly: `ERROR` means
something is objectively broken, `WARNING` means "worth a look", and `INFO` is an
observation. Statistical oddities and duplicates are never hard errors; they're
candidates for review, phrased that way on purpose. The dashboard's accuracy
estimate is labeled an estimate, with its formula on screen.

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

## How it fits together

```text
Dataset ─▶ Loaders ─▶ Normalized model ─▶ Analysis engine ─▶ Issues ─┬─▶ Report  (text)
                        (cvflow.model)      ├─ integrity             │
                                            ├─ annotations           └─▶ Design (dashboard)
                                            ├─ statistics
                                            ├─ duplicates
                                            └─ leakage
```

Everything downstream speaks one normalized model and one `Issue` type, so a new
format, rule, or output slots in without touching the rest. Details in
[`docs/architecture.md`](docs/architecture.md).

## Development

```bash
git clone https://github.com/RizwanMunawar/cvflow
cd cvflow
pip install -e ".[dev]"

ruff check .          # lint
ruff format .         # format
mypy                  # type-check (strict)
pytest                # tests
```

Contributions are welcome. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## License

CVFlow is released under the [MIT License](LICENSE).

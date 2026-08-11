<h1 align="center">🔍 CVFlow</h1>

<p align="center">
  <strong>A linter for computer-vision datasets.</strong><br>
  Point it at a folder of images and labels, and it tells you what's broken,
  duplicated, mislabeled, or suspicious, before it wastes a training run.
</p>

<p align="center">
  <a href="https://github.com/RizwanMunawar/cvflow/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/RizwanMunawar/cvflow/actions/workflows/ci.yml/badge.svg"></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.9%2B-blue">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-green">
</p>

---

## The problem

Most model bugs aren't in the model; they're in the data. A handful of corrupt
JPEGs, a few hundred boxes that spill off the edge of the frame, one class that's
secretly 0.3% of your labels, or the same video frame sitting in both `train`
and `val`. None of it throws an error. It just quietly drags your metrics around
and you find out three experiments later.

Finding this stuff by hand means scrolling through thousands of images. CVFlow
does that scan for you and hands back a short, ranked list of what actually
deserves your attention.

```bash
cvflow inspect ./dataset
```

## What it checks

Point CVFlow at a dataset and it answers the questions you'd otherwise check by
hand, one script at a time:

- **Is anything broken?** Corrupt/unreadable images, missing or invalid
  annotation files, broken paths, bad image dimensions, duplicate filenames.
- **Are the annotations sane?** Boxes outside the image, negative or
  zero-area boxes, absurdly tiny or full-frame boxes, duplicate overlapping
  boxes, class IDs that don't exist.
- **Is the distribution weird?** Class balance, objects per image, box sizes,
  aspect ratios, and images that are statistical outliers.
- **Do I have duplicates?** Exact copies (by hash) and near-duplicates (by
  perceptual hash, with a similarity score).
- **Are my splits leaking?** The same (or nearly the same) image showing up in
  more than one split. This one bites hardest on datasets cut from video.

Every finding comes with a severity, a plain-English reason, where it is, the
evidence behind it, and a suggested next step. CVFlow won't tell you your dataset
is *wrong*; it shows you what looks off and lets you make the call.

## Quick start

```bash
# from a source checkout
pip install -e .

cvflow inspect ./dataset
```

That's it. CVFlow figures out whether the folder is YOLO or COCO, loads it, runs
every check, and prints a report:

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

The exit code is `0` when nothing's wrong, and non-zero when there are errors,
so you can drop `cvflow inspect` straight into CI. (Add `--strict` to fail on
warnings too.)

## How your dataset should be laid out

CVFlow reads the two most common detection formats. The closer your folder is to
one of the layouts below, the more it can audit. In particular, it needs to
find the **actual image files** on disk to check for corrupt images, duplicates,
and split leakage.

### YOLO

The recommended layout is an Ultralytics-style `data.yaml` next to mirrored
`images/` and `labels/` folders:

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

A label file holds **one box per line**, in normalized YOLO format: class id
followed by the box center and size, each as a fraction of the image (0–1):

```text
# class_id  cx     cy     w      h
0           0.512  0.437  0.104  0.216
1           0.300  0.300  0.050  0.080
```

A few things worth knowing:

- CVFlow finds a label by taking the image path and swapping `images/` →
  `labels/` and the extension → `.txt`. Keep that mirroring intact.
- An image with **no label file, or an empty one, is treated as a background
  image** (no objects); that's a WARNING you can sanity-check, not an error.
- Supported image extensions: `.jpg .jpeg .png .bmp .webp .tif .tiff`.

**No `data.yaml`?** CVFlow falls back to a plain `images/` + `labels/` pair. It
picks up `train/`, `val/`, `test/` subfolders if they're there, otherwise treats
everything as one split. Class names are read from a `classes.txt` (one name per
line) if present, and inferred from the label files otherwise.

### COCO

Put your annotation JSON(s) under `annotations/` and the images under `images/`:

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
  top-left. CVFlow normalizes it internally using each image's `width`/`height`,
  so a YOLO box and a COCO box end up meaning the same thing.
- The **split** is inferred from the JSON filename: anything containing `train`,
  `val`, or `test`. A single JSON with no such hint loads as one unnamed split.
- To run the image-level checks (corrupt / duplicate / leakage), CVFlow needs the
  pixels. It looks for each `file_name` under the dataset root, then `images/`,
  then `images/<split>/` and `<split>/`. If it can't find them, it still audits
  structure, annotations, and statistics, and tells you image checks were
  skipped rather than inventing false positives.

> **Rule of thumb:** structure and annotation checks run from the labels alone;
> corrupt-image, duplicate, and leakage checks need the image files reachable
> from the dataset root. Point CVFlow at the folder that contains both.

## Options

```text
cvflow inspect <path> [options]

  -f, --format {yolo,coco}   Force a format instead of auto-detecting.
      --no-images            Skip checks that read image bytes (much faster;
                             also skips corrupt/duplicate/leakage detection).
      --no-stats             Hide the dataset-statistics section.
      --strict               Exit non-zero on warnings, not just errors.
```

Exit codes: `0` clean, `1` problems found (errors, or warnings under `--strict`),
`2` bad usage, `3` path not found, `4` the dataset couldn't be loaded.

## Design philosophy

> Don't tell developers their dataset is wrong. Show them what looks suspicious,
> explain why, and let them decide.

That principle is baked into the tool. Severity is used honestly:
`ERROR` means something is objectively broken, `WARNING` means "worth a look",
and `INFO` is just an observation. Statistical oddities and duplicates are never
hard errors; they're candidates for review, phrased that way on purpose.

## Roadmap

- ✅ **Project foundation**: CLI, packaging, model, tests, CI
- ✅ **Dataset loaders**: YOLO & COCO → one normalized model
- ✅ **Integrity analysis**: corrupt images, missing/invalid annotations
- ✅ **Annotation analysis**: bounding-box validation & anomalies
- ✅ **Dataset statistics**: distributions & outlier detection
- ✅ **Duplicate detection**: exact + perceptual hashing
- ✅ **Split-leakage detection**: cross-split similarity
- ⬜ **Visualization**: eyeball the flagged samples

## How it fits together

```text
Dataset ─▶ Loaders ─▶ Normalized model ─▶ Analysis engine ─▶ Issues ─▶ Report
                        (cvflow.model)      ├─ integrity
                                            ├─ annotations
                                            ├─ statistics
                                            ├─ duplicates
                                            └─ leakage
```

Everything downstream speaks in one normalized model and one `Issue` type, so a
new format, rule, or output slots in without touching the rest. The details live
in [`docs/architecture.md`](docs/architecture.md).

## Development

```bash
pip install -e ".[dev]"

ruff check .          # lint
ruff format .         # format
mypy                  # type-check (strict)
pytest                # tests
```

Contributions are welcome. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Connect

<p>
  <a href="https://rizwanai.com"><img alt="Website" src="https://img.shields.io/badge/Website-rizwanai.com-2ea44f?style=for-the-badge&logo=googlechrome&logoColor=white"></a>
  <a href="https://github.com/RizwanMunawar"><img alt="GitHub" src="https://img.shields.io/badge/GitHub-RizwanMunawar-181717?style=for-the-badge&logo=github&logoColor=white"></a>
  <a href="https://x.com/muhammdrizwanmr"><img alt="X" src="https://img.shields.io/badge/X-@muhammdrizwanmr-000000?style=for-the-badge&logo=x&logoColor=white"></a>
</p>

## License

CVFlow is released under the [MIT License](LICENSE).

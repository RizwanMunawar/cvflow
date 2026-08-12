"""Normalized dataset representation.

This is the single, format-agnostic model that every analysis stage consumes.
Loaders (YOLO, COCO, …) are responsible for translating their on-disk formats
into these types; nothing downstream needs to know where the data came from.

Coordinate convention
----------------------
Bounding boxes are stored as **normalized ``xyxy``** — ``(x_min, y_min, x_max,
y_max)`` each expressed as a fraction of the image's width/height in ``[0, 1]``.
This lets YOLO (already normalized) and COCO (absolute pixels + known image
dimensions) unify *without* reading image files, and it makes boundary/size
checks (annotation geometry) trivially image-size-independent.

Loaders are deliberately **lenient**: an out-of-range or inverted box is a valid
*representation* of bad data, not something to reject here. Deciding whether a
value is a problem is the analysis engine's job.
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from dataclasses import dataclass, field


@dataclass(frozen=True)
class BoundingBox:
    """A single object-detection annotation in normalized ``xyxy`` form.

    Attributes:
        class_id: Integer class identifier as recorded in the source dataset.
        x_min, y_min, x_max, y_max: Normalized coordinates (fractions of image
            width/height). Values may fall outside ``[0, 1]`` or be inverted for
            invalid source data; that is intentional and left for analysis.
        points: The annotation's *original* geometry when it was not an
            axis-aligned box: a segmentation polygon's vertices, or an oriented
            box's four corners, as normalized ``(x, y)`` pairs. ``None`` for
            plain detection boxes.

            Every check can therefore keep working on the extent above, while
            the ones that care about masks or rotation read the real shape here
            instead of pretending a polygon is a rectangle.
    """

    class_id: int
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    points: tuple[tuple[float, float], ...] | None = None

    @property
    def width(self) -> float:
        """Normalized width (may be zero or negative for invalid boxes)."""
        return self.x_max - self.x_min

    @property
    def height(self) -> float:
        """Normalized height (may be zero or negative for invalid boxes)."""
        return self.y_max - self.y_min

    @property
    def area(self) -> float:
        """Normalized area. Clamped to ``0`` when either side is non-positive."""
        w, h = self.width, self.height
        if w <= 0 or h <= 0:
            return 0.0
        return w * h

    @property
    def center(self) -> tuple[float, float]:
        """Normalized ``(cx, cy)`` center point."""
        return ((self.x_min + self.x_max) / 2.0, (self.y_min + self.y_max) / 2.0)

    @property
    def polygon_area(self) -> float:
        """Area enclosed by :attr:`points` (shoelace), or ``0`` without them.

        Normalized like :attr:`area`, so the two are directly comparable, which
        is what tells a real mask from a rectangle drawn as one.
        """
        if not self.points or len(self.points) < 3:
            return 0.0
        total = 0.0
        for index, (x1, y1) in enumerate(self.points):
            x2, y2 = self.points[(index + 1) % len(self.points)]
            total += x1 * y2 - x2 * y1
        return abs(total) / 2.0

    @property
    def fill_ratio(self) -> float:
        """How much of the box the real shape actually covers, in ``[0, 1]``.

        ``1.0`` means the polygon *is* its bounding box.
        """
        box_area = self.area
        if box_area <= 0 or not self.points:
            return 0.0
        return min(self.polygon_area / box_area, 1.0)

    @property
    def rotation(self) -> float:
        """Rotation of a four-cornered box in degrees, in ``[0, 90)``.

        Measured from the first edge. ``0`` for anything without exactly four
        points, which the OBB checks test for first.
        """
        if not self.points or len(self.points) != 4:
            return 0.0
        (x1, y1), (x2, y2) = self.points[0], self.points[1]
        angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
        return angle % 90.0

    @property
    def corner_squareness(self) -> float:
        """Worst corner deviation from a right angle, in degrees.

        An oriented box is a *rectangle* that happens to be rotated; consumers
        rely on that. Four points that do not form one are a broken annotation,
        and this is how far off the worst corner is.
        """
        if not self.points or len(self.points) != 4:
            return 0.0
        worst = 0.0
        for index in range(4):
            ax, ay = self.points[index - 1]
            bx, by = self.points[index]
            cx, cy = self.points[(index + 1) % 4]
            first = (ax - bx, ay - by)
            second = (cx - bx, cy - by)
            len_first = math.hypot(*first)
            len_second = math.hypot(*second)
            if len_first == 0 or len_second == 0:
                return 90.0
            cosine = (first[0] * second[0] + first[1] * second[1]) / (len_first * len_second)
            angle = math.degrees(math.acos(max(-1.0, min(1.0, cosine))))
            worst = max(worst, abs(angle - 90.0))
        return worst

    @classmethod
    def from_yolo(cls, class_id: int, cx: float, cy: float, w: float, h: float) -> BoundingBox:
        """Build from YOLO's normalized ``(cx, cy, w, h)`` center form."""
        return cls(
            class_id=class_id,
            x_min=cx - w / 2.0,
            y_min=cy - h / 2.0,
            x_max=cx + w / 2.0,
            y_max=cy + h / 2.0,
        )

    @classmethod
    def from_coco(
        cls,
        class_id: int,
        x: float,
        y: float,
        w: float,
        h: float,
        image_width: float,
        image_height: float,
    ) -> BoundingBox:
        """Build from COCO's absolute top-left ``(x, y, w, h)`` box.

        Normalizes using the image dimensions. If a dimension is unknown
        (``<= 0``), the absolute values are kept as-is so downstream checks can
        flag the out-of-range coordinates rather than silently hiding them.
        """
        sx = image_width if image_width > 0 else 1.0
        sy = image_height if image_height > 0 else 1.0
        return cls(
            class_id=class_id,
            x_min=x / sx,
            y_min=y / sy,
            x_max=(x + w) / sx,
            y_max=(y + h) / sy,
        )


@dataclass
class ImageItem:
    """One image and its annotations within a dataset.

    Attributes:
        path: Path to the image, as recorded/resolved by the loader. May be
            relative to :attr:`Dataset.root`. Existence is not guaranteed here —
            integrity checks verify it.
        split: Dataset split (``"train"``/``"val"``/``"test"``) or ``None``.
        width, height: Pixel dimensions when known (e.g. from COCO JSON);
            ``None`` for formats that don't record them (e.g. plain YOLO).
        boxes: The image's bounding-box annotations.
        image_id: Source identifier when the format provides one (COCO).
        label_path: Path to the annotation file, when applicable (YOLO).
    """

    path: str
    split: str | None = None
    width: int | None = None
    height: int | None = None
    boxes: list[BoundingBox] = field(default_factory=list)
    image_id: int | None = None
    label_path: str | None = None

    @property
    def is_empty(self) -> bool:
        """True when the image has no annotations."""
        return len(self.boxes) == 0

    @property
    def num_boxes(self) -> int:
        return len(self.boxes)


@dataclass
class Dataset:
    """A loaded dataset in CVFlow's normalized form.

    Attributes:
        name: Human-friendly dataset name (usually the root directory name).
        root: Absolute path to the dataset root.
        format: Source format identifier, e.g. ``"yolo"`` or ``"coco"``.
        task: What the annotations describe: ``"detect"`` (axis-aligned boxes),
            ``"segment"`` (polygons) or ``"obb"`` (oriented boxes). Polygons and
            oriented boxes are stored as their axis-aligned extent so every
            check works on one geometry; this field records what they came from,
            which matters when writing labels back.
        images: All images across all splits.
        class_names: Mapping of class id to class name discovered from the source.
    """

    name: str
    root: str
    format: str
    task: str = "detect"
    images: list[ImageItem] = field(default_factory=list)
    class_names: dict[int, str] = field(default_factory=dict)

    @property
    def num_images(self) -> int:
        return len(self.images)

    @property
    def num_annotations(self) -> int:
        return sum(img.num_boxes for img in self.images)

    @property
    def num_classes(self) -> int:
        return len(self.class_names)

    @property
    def splits(self) -> list[str]:
        """Sorted list of distinct, non-null split names present."""
        return sorted({img.split for img in self.images if img.split is not None})

    def images_in_split(self, split: str) -> list[ImageItem]:
        return [img for img in self.images if img.split == split]

    def iter_boxes(self) -> Iterator[tuple[ImageItem, BoundingBox]]:
        """Iterate over every ``(image, box)`` pair in the dataset."""
        for img in self.images:
            for box in img.boxes:
                yield img, box

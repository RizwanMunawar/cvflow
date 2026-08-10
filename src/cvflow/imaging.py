"""Lightweight image helpers.

Wraps Pillow so the rest of the codebase doesn't import it directly and so the
package still imports if Pillow is somehow unavailable (the helpers then degrade
gracefully rather than crashing). Pillow is a declared runtime dependency.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

try:  # pragma: no cover - import guard
    from PIL import Image

    _PILLOW_AVAILABLE = True
except ImportError:  # pragma: no cover - Pillow is a declared dependency
    _PILLOW_AVAILABLE = False

# dHash parameters: a (HASH_SIZE+1) x HASH_SIZE grayscale thumbnail yields
# HASH_SIZE*HASH_SIZE = 64 comparison bits.
_HASH_SIZE = 8


def pillow_available() -> bool:
    """Whether Pillow is importable (image-byte checks are possible)."""
    return _PILLOW_AVAILABLE


def is_readable_image(path: Path) -> bool:
    """Return True if ``path`` is a decodable image.

    When Pillow is unavailable we cannot judge, so we conservatively return
    True (absence of a checker is not evidence of corruption).
    """
    if not _PILLOW_AVAILABLE:
        return True
    try:
        with Image.open(path) as img:
            img.verify()
        return True
    except Exception:
        # Pillow raises a variety of errors for truncated/garbage files.
        return False


def read_image_size(path: Path) -> tuple[int, int] | None:
    """Return ``(width, height)`` in pixels, or ``None`` if it can't be read."""
    if not _PILLOW_AVAILABLE:
        return None
    try:
        with Image.open(path) as img:
            return (int(img.width), int(img.height))
    except Exception:
        return None


def file_hash(path: Path, *, chunk_size: int = 65536) -> str | None:
    """Return the SHA-256 hex digest of a file's bytes, for exact duplicates.

    Streams the file in chunks so large images don't blow up memory. Returns
    ``None`` if the file can't be read.
    """
    hasher = hashlib.sha256()
    try:
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(chunk_size), b""):
                hasher.update(chunk)
    except OSError:
        return None
    return hasher.hexdigest()


def perceptual_hash(path: Path) -> int | None:
    """Return a 64-bit difference hash (dHash) of an image, or ``None``.

    dHash downsizes to a small grayscale thumbnail and encodes the sign of the
    horizontal gradient between adjacent pixels. Visually similar images produce
    hashes with a small Hamming distance, so it is robust to mild resizing,
    compression, and color shifts. Deterministic and dependency-light (Pillow).
    """
    if not _PILLOW_AVAILABLE:
        return None
    try:
        with Image.open(path) as img:
            small = img.convert("L").resize((_HASH_SIZE + 1, _HASH_SIZE))
            pixels = list(small.tobytes())  # row-major grayscale byte values
    except Exception:
        return None

    bits = 0
    row_stride = _HASH_SIZE + 1
    for row in range(_HASH_SIZE):
        for col in range(_HASH_SIZE):
            left = pixels[row * row_stride + col]
            right = pixels[row * row_stride + col + 1]
            bits = (bits << 1) | (1 if left > right else 0)
    return bits


def hamming_distance(a: int, b: int) -> int:
    """Number of differing bits between two hashes."""
    return bin(a ^ b).count("1")  # 3.9-compatible popcount

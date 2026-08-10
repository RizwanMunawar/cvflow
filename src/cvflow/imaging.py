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

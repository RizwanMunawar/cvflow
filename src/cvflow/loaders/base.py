"""Loader abstraction.

A :class:`DatasetLoader` knows how to recognize one on-disk dataset format and
translate it into the normalized :class:`cvflow.model.Dataset`. Adding a new
format means adding a loader and registering it — nothing downstream changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from cvflow.model import Dataset

# Common image extensions recognized across loaders.
IMAGE_EXTENSIONS: frozenset[str] = frozenset(
    {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}
)


class DatasetLoader(ABC):
    """Base class for all dataset loaders."""

    #: Short, stable format identifier, e.g. ``"yolo"`` or ``"coco"``.
    format: str = ""

    @abstractmethod
    def detect(self, path: Path) -> bool:
        """Return ``True`` if ``path`` looks like this loader's format.

        Detection must be cheap and side-effect free: inspect names and a small
        amount of file content, never load the whole dataset.
        """

    @abstractmethod
    def load(self, path: Path) -> Dataset:
        """Load the dataset rooted at ``path`` into the normalized model.

        Raises:
            cvflow.exceptions.DatasetError: If the dataset cannot be loaded.
        """

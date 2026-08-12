"""The sample dataset, for when you just want to see what CVFlow does.

``cvflow inspect`` with no path fetches Ultralytics' ``coco128`` (a 128-image
slice of COCO), unzips it into a cache directory, and inspects that. It is
downloaded once and reused, so the second run is instant and offline.

Standard library only: :mod:`urllib` for the fetch, :mod:`zipfile` for the
unpack. Nothing here runs unless the user omits the path.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import urllib.error
import urllib.request
import zipfile
from collections.abc import Callable
from pathlib import Path

from cvflow.exceptions import DatasetError

#: Ultralytics' published sample. Small (~7 MB) and a real dataset, warts and all.
SAMPLE_URL = "https://github.com/ultralytics/assets/releases/download/v0.0.0/coco128.zip"

#: The directory the archive unpacks into.
SAMPLE_NAME = "coco128"

_USER_AGENT = "cvflow"


def cache_dir() -> Path:
    """Where downloaded samples live.

    ``CVFLOW_CACHE`` wins if set; otherwise the platform's usual cache home.
    """
    override = os.environ.get("CVFLOW_CACHE")
    if override:
        return Path(override)
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local"
        return Path(base) / "cvflow" / "cache"
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "cvflow"


def ensure_sample(
    *,
    url: str = SAMPLE_URL,
    name: str = SAMPLE_NAME,
    dest: Path | None = None,
    echo: Callable[[str], None] = lambda message: None,
) -> Path:
    """Return a local path to the sample dataset, downloading it if needed.

    Args:
        url: Archive to fetch. Overridable so tests can point at a local file.
        name: Directory the archive is expected to unpack into.
        dest: Cache directory. Defaults to :func:`cache_dir`.
        echo: Where to report progress; silent by default.

    Raises:
        DatasetError: The download or the archive failed. The message says
            which, and what to do instead.
    """
    root = (dest or cache_dir()).expanduser()
    target = root / name
    if _looks_populated(target):
        echo(f"Using the cached {name} sample at {target}")
        return target

    root.mkdir(parents=True, exist_ok=True)
    echo(f"No dataset given, so fetching the {name} sample (about 7 MB) from {url}")

    with tempfile.TemporaryDirectory() as scratch:
        archive = Path(scratch) / "sample.zip"
        _download(url, archive)
        _extract(archive, root)

    if not _looks_populated(target):
        # Some archives unpack their contents flat rather than into a folder.
        target = root if _looks_populated(root) else target
    if not _looks_populated(target):
        raise DatasetError(f"the downloaded archive did not contain a {name} dataset")

    echo(f"Sample ready at {target}")
    return target


def _looks_populated(path: Path) -> bool:
    return path.is_dir() and any(path.iterdir())


def _download(url: str, target: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=60) as response, target.open("wb") as handle:
            shutil.copyfileobj(response, handle)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise DatasetError(
            f"could not download the sample dataset ({exc}). "
            "Check your connection, or pass a dataset path instead."
        ) from exc


def _extract(archive: Path, dest: Path) -> None:
    """Unpack the archive, refusing members that would escape ``dest``.

    A zip can name ``../`` or an absolute path for its members, which would
    write outside the cache. Every member is resolved and checked first.
    """
    try:
        with zipfile.ZipFile(archive) as bundle:
            root = dest.resolve()
            for member in bundle.namelist():
                resolved = (root / member).resolve()
                if resolved != root and root not in resolved.parents:
                    raise DatasetError(f"refusing to unpack a path outside the cache: {member}")
            bundle.extractall(dest)
    except zipfile.BadZipFile as exc:
        raise DatasetError(f"the downloaded sample is not a valid zip archive ({exc})") from exc

"""Dataset-scoped image inspection cache with bounded parallel I/O.

Persist only derived facts, never pixels. Changes to size or modification time
invalidate a cached entry; use --no-cache to force a complete rescan.
"""
from __future__ import annotations

import contextlib
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from cvflow.imaging import file_hash, is_readable_image, perceptual_hash

_VERSION = 1


class ImageScanCache:
    def __init__(self, cache_path: Path | None = None, workers: int = 1) -> None:
        self.path = cache_path
        self.workers = max(1, workers)
        self._data: dict[str, dict[str, object]] = {}
        if cache_path is not None:
            try:
                payload = json.loads(cache_path.read_text(encoding="utf-8"))
                if payload.get("version") == _VERSION and isinstance(payload.get("entries"), dict):
                    self._data = payload["entries"]
            except (OSError, ValueError, AttributeError, TypeError):
                pass

    def scan(self, paths: list[Path]) -> None:
        """Calculate each changed image once, using threads for independent files."""
        unique = list(dict.fromkeys(str(path.resolve()) for path in paths))
        pending: list[tuple[str, Path, int, int]] = []
        for key in unique:
            path = Path(key)
            try:
                stat = path.stat()
            except OSError:
                self._data.pop(key, None)
                continue
            entry = self._data.get(key)
            if (
                entry is not None
                and entry.get("size") == stat.st_size
                and entry.get("mtime_ns") == stat.st_mtime_ns
            ):
                continue
            pending.append((key, path, stat.st_size, stat.st_mtime_ns))

        def inspect(task: tuple[str, Path, int, int]) -> tuple[str, dict[str, object]]:
            key, path, size, mtime_ns = task
            return key, {
                "size": size, "mtime_ns": mtime_ns,
                "readable": is_readable_image(path),
                "sha256": file_hash(path),
                "dhash": perceptual_hash(path),
            }

        if self.workers == 1:
            results = map(inspect, pending)
            for key, entry in results:
                self._data[key] = entry
        else:
            with ThreadPoolExecutor(max_workers=self.workers) as pool:
                for key, entry in pool.map(inspect, pending):
                    self._data[key] = entry

    def result(self, path: Path, field: str) -> object | None:
        return self._data.get(str(path.resolve()), {}).get(field)

    def save(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + f".{os.getpid()}.tmp")
        try:
            tmp.write_text(
                json.dumps({"version": _VERSION, "entries": self._data}),
                encoding="utf-8",
            )
            os.replace(tmp, self.path)
        finally:
            with contextlib.suppress(FileNotFoundError):
                tmp.unlink()

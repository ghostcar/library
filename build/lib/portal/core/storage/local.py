"""Storage port (master prompt 2.2: StorageAdapter) and content-addressed layout.

Layout (master prompt 6.2):
  originals/<sha2>/<sha>.<ext>
  derivatives/<sha2>/<sha>.<ext>
  quarantine/<job-id>/
Originals are immutable: the adapter exposes no delete for them.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class StorageError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class StoredObject:
    storage_path: str  # relative path inside the storage root
    sha256: str
    size_bytes: int


class StorageAdapter(Protocol):
    async def save(self, area: str, content: bytes, extension: str) -> StoredObject: ...
    async def open(self, storage_path: str) -> bytes: ...
    async def exists(self, storage_path: str) -> bool: ...
    async def remove(self, storage_path: str) -> None: ...


class LocalStorageAdapter:
    """Content-addressed local filesystem storage."""

    def __init__(self, root: Path) -> None:
        self._root = root
        root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, storage_path: str) -> Path:
        candidate = (self._root / storage_path).resolve()
        if not candidate.is_relative_to(self._root.resolve()):
            msg = f"path traversal rejected: {storage_path!r}"
            raise StorageError(msg)
        return candidate

    async def save(self, area: str, content: bytes, extension: str) -> StoredObject:
        if area not in {"originals", "derivatives", "quarantine", "exports"}:
            msg = f"unknown storage area: {area!r}"
            raise StorageError(msg)
        sha = _sha256_hex(content)
        ext = extension.lstrip(".")
        relative = f"{area}/{sha[:2]}/{sha}.{ext}"
        target = self._resolve(relative)
        if target.exists():
            return StoredObject(relative, sha, len(content))  # content-addressed: identical
        await self._write(target, content)
        return StoredObject(relative, sha, len(content))

    async def save_raw(self, area: str, relative_name: str, content: bytes) -> StoredObject:
        """Store under an explicit name (quarantine batches), not content-addressed."""
        if area not in {"quarantine", "exports"}:
            msg = f"save_raw is only allowed for quarantine/exports, got {area!r}"
            raise StorageError(msg)
        relative = f"{area}/{relative_name.lstrip('/')}"
        target = self._resolve(relative)
        await self._write(target, content)
        return StoredObject(relative, _sha256_hex(content), len(content))

    async def _write(self, target: Path, content: bytes) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".tmp")
        tmp.write_bytes(content)
        tmp.replace(target)

    async def open(self, storage_path: str) -> bytes:
        target = self._resolve(storage_path)
        if not target.is_file():
            msg = f"object not found: {storage_path}"
            raise StorageError(msg)
        return target.read_bytes()

    async def exists(self, storage_path: str) -> bool:
        return self._resolve(storage_path).is_file()

    async def remove(self, storage_path: str) -> None:
        if storage_path.startswith("originals/"):
            msg = "originals are immutable and cannot be removed via storage adapter"
            raise StorageError(msg)
        target = self._resolve(storage_path)
        if target.is_file():
            target.unlink()


def _sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()

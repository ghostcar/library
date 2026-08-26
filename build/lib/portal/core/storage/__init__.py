"""Portal core: storage (master prompt 2.2 StorageAdapter)."""

from __future__ import annotations

from portal.core.storage.local import (
    LocalStorageAdapter,
    StorageAdapter,
    StorageError,
    StoredObject,
)

__all__ = ["LocalStorageAdapter", "StorageAdapter", "StorageError", "StoredObject"]

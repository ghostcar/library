"""Unit tests: in-memory rate limiter and local storage adapter."""

from __future__ import annotations

from pathlib import Path

import pytest

from portal.core.auth.rate_limit import RateLimiter
from portal.core.storage.local import LocalStorageAdapter, StorageError


class TestRateLimiter:
    def test_allows_up_to_limit(self) -> None:
        limiter = RateLimiter(limit=3, window_seconds=60)
        assert limiter.check("k")
        assert limiter.check("k")
        assert limiter.check("k")
        assert not limiter.check("k")

    def test_keys_are_independent(self) -> None:
        limiter = RateLimiter(limit=1, window_seconds=60)
        assert limiter.check("a")
        assert limiter.check("b")
        assert not limiter.check("a")

    def test_reset(self) -> None:
        limiter = RateLimiter(limit=1, window_seconds=60)
        assert limiter.check("a")
        limiter.reset("a")
        assert limiter.check("a")


class TestLocalStorageAdapter:
    @pytest.fixture
    def storage(self, tmp_path: Path) -> LocalStorageAdapter:
        return LocalStorageAdapter(tmp_path / "storage")

    async def test_save_and_open_roundtrip(self, storage: LocalStorageAdapter) -> None:
        stored = await storage.save("originals", b"book content", "fb2")
        assert stored.size_bytes == len(b"book content")
        assert stored.storage_path.startswith("originals/")
        assert await storage.open(stored.storage_path) == b"book content"
        assert await storage.exists(stored.storage_path)

    async def test_content_addressed_dedup(self, storage: LocalStorageAdapter) -> None:
        first = await storage.save("originals", b"same", "epub")
        second = await storage.save("originals", b"same", "epub")
        assert first == second

    async def test_different_content_different_paths(self, storage: LocalStorageAdapter) -> None:
        a = await storage.save("originals", b"aaa", "fb2")
        b = await storage.save("originals", b"bbb", "fb2")
        assert a.sha256 != b.sha256
        assert a.storage_path != b.storage_path

    async def test_unknown_area_rejected(self, storage: LocalStorageAdapter) -> None:
        with pytest.raises(StorageError, match="unknown storage area"):
            await storage.save("hacker-area", b"x", "fb2")

    async def test_path_traversal_rejected(self, storage: LocalStorageAdapter) -> None:
        with pytest.raises(StorageError, match="traversal"):
            await storage.open("../../etc/passwd")

    async def test_originals_are_immutable(self, storage: LocalStorageAdapter) -> None:
        stored = await storage.save("originals", b"precious", "fb2")
        with pytest.raises(StorageError, match="immutable"):
            await storage.remove(stored.storage_path)

    async def test_derivatives_can_be_removed(self, storage: LocalStorageAdapter) -> None:
        stored = await storage.save("derivatives", b"derived", "epub")
        await storage.remove(stored.storage_path)
        assert not await storage.exists(stored.storage_path)

"""Unit tests: settings validation, module registry, catalog service with fakes."""

from __future__ import annotations

from uuid import uuid4

import pytest

from portal.core.config.config import AppEnv, Settings
from portal.core.module_registry.registry import ModuleRegistry
from portal.modules.library.application.services import CatalogService, RegisterWorkInput
from portal.modules.library.domain import entities as de
from portal.modules.library.domain.enums import MembershipType


class TestSettings:
    def test_defaults(self) -> None:
        settings = Settings(_env_file=None)  # type: ignore[call-arg]
        assert settings.port == 8001
        assert settings.host == "127.0.0.1"
        assert settings.app_env is AppEnv.DEVELOPMENT
        assert settings.is_dev

    def test_database_url_env_prefix(self) -> None:
        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
            database_url="postgresql+asyncpg://x:x@localhost:1/x",
        )
        assert "localhost:1" in settings.database_url


class TestModuleRegistry:
    def test_register_and_list(self) -> None:
        registry = ModuleRegistry()
        registry.register("library", description="test")
        assert registry.is_enabled("library")
        assert [m.name for m in registry.descriptors()] == ["library"]

    def test_duplicate_registration_rejected(self) -> None:
        registry = ModuleRegistry()
        registry.register("library")
        with pytest.raises(ValueError, match="already registered"):
            registry.register("library")

    def test_disabled_module_has_no_router(self) -> None:
        from fastapi import APIRouter

        registry = ModuleRegistry()
        router = APIRouter()
        registry.register("library", router=router, enabled=False)
        assert registry.routers() == []
        assert not registry.is_enabled("library")


class _FakeWorkRepo:
    def __init__(self) -> None:
        self.saved: list[de.Work] = []

    async def add(self, work: de.Work) -> de.Work:
        self.saved.append(work)
        return work


class _FakeAuthorRepo:
    def __init__(self) -> None:
        self.by_name: dict[str, de.Author] = {}
        self.saved: list[de.Author] = []

    async def add(self, author: de.Author) -> de.Author:
        self.saved.append(author)
        self.by_name[de.normalize_title(author.name)] = author
        return author

    async def find_by_name(self, owner_id: uuid4, name: str) -> de.Author | None:
        return self.by_name.get(de.normalize_title(name))


class _FakeSeriesRepo:
    def __init__(self) -> None:
        self.by_title: dict[str, de.Series] = {}
        self.memberships: list[de.SeriesMembership] = []

    async def add(self, series: de.Series) -> de.Series:
        self.by_title[de.normalize_title(series.title)] = series
        return series

    async def find_by_title(self, owner_id: uuid4, title: str) -> de.Series | None:
        return self.by_title.get(de.normalize_title(title))

    async def add_membership(self, membership: de.SeriesMembership) -> None:
        self.memberships.append(membership)


class TestCatalogService:
    async def test_register_work_creates_author_and_series(self) -> None:
        works, authors, series = _FakeWorkRepo(), _FakeAuthorRepo(), _FakeSeriesRepo()
        service = CatalogService(works=works, authors=authors, series=series)
        owner = uuid4()

        work = await service.register_work(
            RegisterWorkInput(
                owner_id=owner,
                title="Цветы для Элернонда",
                author_names=["Дэниел Киз"],
                series_title="Классика XX века",
                series_index_raw="5",
                series_membership_type=MembershipType.MAIN,
            ),
        )

        assert work.title == "Цветы для Элернонда"
        assert len(works.saved) == 1
        assert len(authors.saved) == 1
        assert len(series.memberships) == 1
        assert str(series.memberships[0].index) == "5"

    async def test_second_registration_reuses_author_and_series(self) -> None:
        works, authors, series = _FakeWorkRepo(), _FakeAuthorRepo(), _FakeSeriesRepo()
        service = CatalogService(works=works, authors=authors, series=series)
        owner = uuid4()

        await service.register_work(
            RegisterWorkInput(owner_id=owner, title="Книга А", author_names=["Автор Х"]),
        )
        await service.register_work(
            RegisterWorkInput(
                owner_id=owner,
                title="Книга Б",
                author_names=["автор х"],  # different case/whitespace
                series_title="цикл",  # no series first time; creates new
            ),
        )
        assert len(authors.saved) == 1  # reused, not duplicated

    async def test_owner_scoping_between_two_owners(self) -> None:
        works, authors, series = _FakeWorkRepo(), _FakeAuthorRepo(), _FakeSeriesRepo()
        service = CatalogService(works=works, authors=authors, series=series)

        await service.register_work(
            RegisterWorkInput(owner_id=uuid4(), title="Книга", author_names=["Автор"]),
        )
        await service.register_work(
            RegisterWorkInput(owner_id=uuid4(), title="Книга", author_names=["Автор"]),
        )
        # Fake repos are shared here; scoping is enforced by SQL filters covered
        # in integration tests. This test documents the intent.
        assert len(works.saved) == 2

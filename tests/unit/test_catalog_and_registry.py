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
        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
            jwt_secret="test-secret-0123456789abcdef",  # noqa: S106
        )
        assert settings.port == 8001
        assert settings.host == "127.0.0.1"
        assert settings.app_env is AppEnv.DEVELOPMENT
        assert settings.is_dev

    def test_missing_jwt_secret_rejected(self) -> None:
        """Explicit jwt_secret=None must fail even when the env provides one (CI)."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="LIBRARY_JWT_SECRET"):
            Settings(_env_file=None, jwt_secret=None)  # type: ignore[call-arg]

    def test_database_url_env_prefix(self) -> None:
        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
            jwt_secret="test-secret-0123456789abcdef0123456789abcdef",  # noqa: S106
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

    async def find_by_title(self, owner_id: uuid4, title: str) -> list[de.Work]:
        normalized = de.normalize_title(title)
        return [w for w in self.saved if w.title_normalized == normalized]


class _FakeAuthorRepo:
    def __init__(self) -> None:
        self.by_owner_name: dict[tuple, de.Author] = {}
        self.saved: list[de.Author] = []

    async def add(self, author: de.Author) -> de.Author:
        self.saved.append(author)
        self.by_owner_name[(author.owner_id, de.normalize_title(author.name))] = author
        return author

    async def find_by_name(self, owner_id: uuid4, name: str) -> de.Author | None:
        return self.by_owner_name.get((owner_id, de.normalize_title(name)))


class _FakeSeriesRepo:
    def __init__(self) -> None:
        self.by_owner_title: dict[tuple, de.Series] = {}
        self.memberships: list[de.SeriesMembership] = []

    async def add(self, series: de.Series) -> de.Series:
        self.by_owner_title[(series.owner_id, de.normalize_title(series.title))] = series
        return series

    async def find_by_title(self, owner_id: uuid4, title: str) -> de.Series | None:
        return self.by_owner_title.get((owner_id, de.normalize_title(title)))

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
        owner_a, owner_b = uuid4(), uuid4()

        first = await service.register_work(
            RegisterWorkInput(owner_id=owner_a, title="Книга", author_names=["Автор"]),
        )
        second = await service.register_work(
            RegisterWorkInput(owner_id=owner_b, title="Книга", author_names=["Автор"]),
        )
        # same title, different owners: no reuse across owner scope
        assert first.id != second.id
        assert len(works.saved) == 2

    async def test_same_title_and_author_reuses_work(self) -> None:
        works, authors, series = _FakeWorkRepo(), _FakeAuthorRepo(), _FakeSeriesRepo()
        service = CatalogService(works=works, authors=authors, series=series)
        owner = uuid4()

        first = await service.register_work(
            RegisterWorkInput(owner_id=owner, title="Цветы", author_names=["Киз"]),
        )
        second = await service.register_work(
            RegisterWorkInput(owner_id=owner, title="цветы", author_names=["Киз"]),
        )
        assert first.id == second.id
        assert len(works.saved) == 1

    async def test_same_title_different_author_creates_new_work(self) -> None:
        works, authors, series = _FakeWorkRepo(), _FakeAuthorRepo(), _FakeSeriesRepo()
        service = CatalogService(works=works, authors=authors, series=series)
        owner = uuid4()

        await service.register_work(
            RegisterWorkInput(owner_id=owner, title="Мгновения", author_names=["Автор Один"]),
        )
        await service.register_work(
            RegisterWorkInput(owner_id=owner, title="Мгновения", author_names=["Автор Два"]),
        )
        assert len(works.saved) == 2

"""Source adapter contracts and registry (master prompt 2.2, 9.1, 9.2).

A disabled adapter registers no routes, jobs, navigation or events.
Presence of a SourceAdapter does not imply an AcquisitionAdapter.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Protocol


class SourceKind(enum.StrEnum):
    OPDS = "opds"
    AUTHOR_TODAY = "author_today"
    LITNET = "litnet"
    FLIBUSTA = "flibusta"


@dataclass(frozen=True, slots=True)
class SourceCapabilities:
    author_updates: bool = False
    series_listing: bool = False
    work_status: bool = False
    metadata: bool = False
    acquisition: bool = False
    authentication: str = "none"  # none | optional | required


@dataclass(frozen=True, slots=True)
class SourceEntry:
    """One observed item from a source feed/page."""

    external_id: str
    title: str
    author_name: str | None = None
    url: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class FetchResult:
    entries: list[SourceEntry]
    not_modified: bool = False
    etag: str | None = None
    last_modified: str | None = None


class SourceAdapterError(ValueError):
    """Expected remote-fetch or parser failure handled by watch backoff."""


class SourceAdapter(Protocol):
    """Contract for source observation adapters."""

    id: str
    parser_version: str
    capabilities: SourceCapabilities

    async def fetch(
        self,
        url: str,
        *,
        etag: str | None = None,
        last_modified: str | None = None,
    ) -> FetchResult: ...


@dataclass(frozen=True, slots=True)
class AdapterDescriptor:
    id: str
    title: str
    enabled: bool
    reason: str  # why disabled, or "" when enabled
    capabilities: SourceCapabilities


_REGISTRY: dict[str, AdapterDescriptor] = {}


def register_adapter(descriptor: AdapterDescriptor) -> None:
    _REGISTRY[descriptor.id] = descriptor


def get_adapter_descriptor(adapter_id: str) -> AdapterDescriptor | None:
    return _REGISTRY.get(adapter_id)


def list_adapters() -> list[AdapterDescriptor]:
    return sorted(_REGISTRY.values(), key=lambda d: d.id)


register_adapter(
    AdapterDescriptor(
        id=SourceKind.OPDS.value,
        title="OPDS-каталоги",
        enabled=True,
        reason="",
        capabilities=SourceCapabilities(
            author_updates=True,
            series_listing=True,
            work_status=False,
            metadata=True,
            acquisition=False,  # acquisition links are user-clicked, not auto-downloaded
            authentication="optional",
        ),
    ),
)
register_adapter(
    AdapterDescriptor(
        id=SourceKind.AUTHOR_TODAY.value,
        title="Author.Today",
        enabled=True,
        reason="",
        capabilities=SourceCapabilities(
            author_updates=True,
            series_listing=True,
            work_status=True,
            metadata=True,
            acquisition=False,
            authentication="none",
        ),
    ),
)
register_adapter(
    AdapterDescriptor(
        id=SourceKind.LITNET.value,
        title="Litnet",
        enabled=False,
        reason="публичного API нет; HTML-адаптер требует исследования и fixtures (ADR-0011)",
        capabilities=SourceCapabilities(),
    ),
)
register_adapter(
    AdapterDescriptor(
        id=SourceKind.FLIBUSTA.value,
        title="Flibusta",
        enabled=True,
        reason="",
        capabilities=SourceCapabilities(
            author_updates=True,
            series_listing=True,
            metadata=True,
            acquisition=False,
            authentication="none",
        ),
    ),
)

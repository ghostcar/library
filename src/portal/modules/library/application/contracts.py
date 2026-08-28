"""Formal adapter contracts for optional library integrations.

The contracts describe boundaries, not implementations.  A capability must be
advertised explicitly before a module exposes routes, jobs, or UI for it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from portal.modules.library.adapters.sources import FetchResult


@dataclass(frozen=True, slots=True)
class AdapterCapabilities:
    import_books: bool = False
    metadata: bool = False
    normalization: bool = False
    validation: bool = False
    notifications: bool = False
    ai_matching: bool = False
    reader_delivery: bool = False


@runtime_checkable
class SourceAdapterContract(Protocol):
    id: str
    capabilities: object

    async def fetch(
        self,
        url: str,
        *,
        etag: str | None = None,
        last_modified: str | None = None,
    ) -> FetchResult: ...


@runtime_checkable
class ImportAdapterContract(Protocol):
    id: str
    capabilities: AdapterCapabilities

    async def inspect(self, filename: str, content: bytes) -> object: ...


@runtime_checkable
class NotificationAdapterContract(Protocol):
    id: str
    capabilities: AdapterCapabilities

    async def send(self, recipient: str, subject: str, body: str) -> None: ...


@dataclass(frozen=True, slots=True)
class AdapterRegistration:
    id: str
    title: str
    enabled: bool
    reason: str
    capabilities: AdapterCapabilities


def validate_registration(registration: AdapterRegistration) -> None:
    """Reject contradictory registrations early (especially disabled adapters)."""
    if registration.enabled and registration.reason:
        raise ValueError("enabled adapter must not have a disable reason")
    if not registration.id.strip():
        raise ValueError("adapter id must not be empty")

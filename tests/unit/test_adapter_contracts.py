"""Tests for explicit optional-adapter contracts."""

from __future__ import annotations

import pytest

from portal.modules.library.adapters.author_today_adapter import AuthorTodayAdapter
from portal.modules.library.adapters.opds_adapter import OPDSAdapter
from portal.modules.library.application.contracts import (
    AdapterRegistration,
    SourceAdapterContract,
    validate_registration,
)


def test_opds_implements_source_contract() -> None:
    assert isinstance(OPDSAdapter(), SourceAdapterContract)
    assert OPDSAdapter().id == "opds"


def test_author_today_implements_source_contract() -> None:
    assert isinstance(AuthorTodayAdapter(), SourceAdapterContract)
    assert AuthorTodayAdapter().id == "author_today"


def test_registration_rejects_enabled_reason() -> None:
    with pytest.raises(ValueError, match="disable reason"):
        validate_registration(AdapterRegistration("x", "X", True, "disabled", object()))


def test_registration_rejects_empty_id() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        validate_registration(AdapterRegistration(" ", "X", False, "disabled", object()))

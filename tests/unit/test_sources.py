"""Unit tests: OPDS parsing, backoff, adapter registry."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from portal.modules.library.adapters.opds_adapter import (
    OPDSParseError,
    parse_opds_feed,
)
from portal.modules.library.adapters.sources import get_adapter_descriptor, list_adapters
from portal.modules.library.adapters.watch_service import next_poll_after

FEED = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:opds="http://opds-spec.org/2010/catalog">
  <id>urn:uuid:feed-1</id>
  <title>Тестовая полка</title>
  <updated>2026-08-26T00:00:00Z</updated>
  <entry>
    <id>urn:uuid:book-1</id>
    <title>Книга первая</title>
    <updated>2026-08-25T10:00:00Z</updated>
    <author><name>Автор Один</name></author>
    <link rel="http://opds-spec.org/acquisition" href="/books/1.fb2" type="application/fb2+xml"/>
  </entry>
  <entry>
    <id>urn:uuid:book-2</id>
    <title>Книга вторая</title>
    <updated>2026-08-25T11:00:00Z</updated>
  </entry>
  <entry>
    <title>Без id — пропустить</title>
    <updated>2026-08-25T12:00:00Z</updated>
  </entry>
</feed>
"""


class TestParseOPDS:
    def test_entries_extracted(self) -> None:
        entries = parse_opds_feed(FEED.encode())
        assert len(entries) == 2
        assert entries[0].external_id == "urn:uuid:book-1"
        assert entries[0].title == "Книга первая"
        assert entries[0].author_name == "Автор Один"
        assert entries[0].url == "/books/1.fb2"

    def test_entry_without_id_skipped(self) -> None:
        entries = parse_opds_feed(FEED.encode())
        assert all(e.external_id for e in entries)

    def test_invalid_xml_rejected(self) -> None:
        with pytest.raises(OPDSParseError):
            parse_opds_feed(b"<not-a-feed/>")

    def test_non_feed_root_rejected(self) -> None:
        xml = '<?xml version="1.0"?><html xmlns="http://www.w3.org/2005/Atom"><body/></html>'
        with pytest.raises(OPDSParseError, match="not an Atom feed"):
            parse_opds_feed(xml.encode())

    def test_xxe_not_resolved(self) -> None:
        evil = (
            b'<?xml version="1.0"?>'
            b'<!DOCTYPE feed [<!ENTITY x SYSTEM "file:///etc/passwd">]>'
            b'<feed xmlns="http://www.w3.org/2005/Atom">'
            b"<id>&x;</id><title>t</title></feed>"
        )
        entries = parse_opds_feed(evil)
        assert entries == []  # no id resolved from filesystem


class TestBackoff:
    def test_success_uses_interval(self) -> None:
        now = datetime.now(UTC)
        nxt = next_poll_after(0, 3600)
        assert timedelta(minutes=59) < nxt - now <= timedelta(minutes=61)

    def test_failure_exponential(self) -> None:
        now = datetime.now(UTC)
        first = next_poll_after(1, 60)
        second = next_poll_after(2, 60)
        third = next_poll_after(3, 60)
        d1 = (first - now).total_seconds()
        d2 = (second - now).total_seconds()
        d3 = (third - now).total_seconds()
        assert 300 <= d1 <= 300 + 60
        assert 600 <= d2 <= 600 + 60
        assert 1200 <= d3 <= 1200 + 60

    def test_backoff_capped(self) -> None:
        now = datetime.now(UTC)
        nxt = next_poll_after(20, 60)
        assert nxt - now <= timedelta(seconds=6 * 3600 + 60, milliseconds=10)


class TestRegistry:
    def test_opds_profiles_and_html_adapters(self) -> None:
        adapters = {a.id: a for a in list_adapters()}
        assert adapters["opds"].enabled
        assert not adapters["author_today"].enabled
        assert adapters["author_today"].reason
        assert adapters["flibusta"].enabled
        assert adapters["flibusta"].capabilities.metadata
        assert not adapters["flibusta"].capabilities.acquisition

    def test_capabilities_distinct_from_acquisition(self) -> None:
        opds = get_adapter_descriptor("opds")
        assert opds is not None
        assert opds.capabilities.metadata
        assert not opds.capabilities.acquisition  # observation != acquisition

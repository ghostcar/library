"""OPDS source adapter (master prompt 9.1): Atom feeds, conditional GET.

Standards-based first-queue source. No protection bypass; authentication
is optional and credentials come from config/env only, never the DB.
Parser version is stored with every observation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import httpx
from lxml import etree

from portal.modules.library.adapters.sources import (
    FetchResult,
    SourceAdapterError,
    SourceCapabilities,
    SourceEntry,
)

logger = logging.getLogger("library.sources.opds")

PARSER_VERSION = "opds-atom-v1"
_ATOM = "http://www.w3.org/2005/Atom"
_OPDS_NS = "http://opds-spec.org/2010/catalog"
_MAX_FEED_BYTES = 5 * 1024 * 1024  # guard against huge/malicious feeds


class OPDSParseError(SourceAdapterError):
    pass


def safe_parser() -> etree.XMLParser:
    return etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        dtd_validation=False,
        huge_tree=False,
    )


def parse_opds_feed(content: bytes) -> list[SourceEntry]:
    """Extract entries from an OPDS 1.2 (Atom) acquisition/navigation feed."""
    try:
        root = etree.fromstring(content, parser=safe_parser())
    except etree.XMLSyntaxError as exc:
        msg = f"invalid OPDS XML: {exc}"
        raise OPDSParseError(msg) from exc

    if etree.QName(root).localname != "feed":
        msg = "root element is not an Atom feed"
        raise OPDSParseError(msg)

    entries: list[SourceEntry] = []
    for entry in root.findall(f"{{{_ATOM}}}entry"):
        entry_id = (entry.findtext(f"{{{_ATOM}}}id") or "").strip()
        title = (entry.findtext(f"{{{_ATOM}}}title") or "").strip()
        if not entry_id or not title:
            continue
        author_name = entry.findtext(f"{{{_ATOM}}}author/{{{_ATOM}}}name")
        link_href = None
        for link in entry.findall(f"{{{_ATOM}}}link"):
            rel = link.get("rel", "")
            if "acquisition" in rel or rel == "":
                link_href = link.get("href")
                break
        entries.append(
            SourceEntry(
                external_id=entry_id,
                title=title,
                author_name=(author_name or "").strip() or None,
                url=link_href,
                raw={"updated": entry.findtext(f"{{{_ATOM}}}updated") or ""},
            ),
        )
    return entries


@dataclass(slots=True)
class OPDSAdapter:
    """SourceAdapter implementation for OPDS 1.2 feeds."""

    client: httpx.AsyncClient | None = None
    id: str = "opds"
    parser_version: str = PARSER_VERSION
    capabilities: SourceCapabilities = field(
        default_factory=lambda: SourceCapabilities(
            author_updates=True,
            series_listing=True,
            metadata=True,
            acquisition=False,
            authentication="optional",
        ),
    )

    async def fetch(
        self,
        url: str,
        *,
        etag: str | None = None,
        last_modified: str | None = None,
    ) -> FetchResult:
        headers: dict[str, str] = {"Accept": "application/atom+xml, application/xml, text/xml"}
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified

        client = self.client or httpx.AsyncClient(
            timeout=20.0,
            follow_redirects=True,
            headers={"User-Agent": "ghostcar-library/0.1 (personal OPDS reader)"},
        )
        try:
            response = await client.get(url, headers=headers)
        except httpx.HTTPError as exc:
            msg = f"OPDS fetch failed: {exc}"
            raise OPDSParseError(msg) from exc

        if response.status_code == 304:
            return FetchResult(
                entries=[],
                not_modified=True,
                etag=etag,
                last_modified=last_modified,
            )
        if response.status_code != 200:
            msg = f"OPDS fetch returned {response.status_code}"
            raise OPDSParseError(msg)
        if len(response.content) > _MAX_FEED_BYTES:
            msg = "OPDS feed exceeds size guard"
            raise OPDSParseError(msg)

        entries = parse_opds_feed(response.content)
        return FetchResult(
            entries=entries,
            etag=response.headers.get("ETag"),
            last_modified=response.headers.get("Last-Modified"),
        )

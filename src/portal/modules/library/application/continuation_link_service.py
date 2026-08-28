"""Review workflow for continuation links embedded in locally owned FB2 files."""

from __future__ import annotations

import ipaddress
import socket
from datetime import UTC, datetime
from typing import cast
from urllib.parse import urlparse
from uuid import UUID

import httpx
from lxml import html
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from portal.modules.library.domain.entities import normalize_title
from portal.modules.library.infrastructure.continuation_links import extract_continuation_links
from portal.modules.library.infrastructure.continuation_orm import ContinuationLinkCandidateModel
from portal.modules.library.infrastructure.orm import WorkModel

_MAX_HTML_BYTES = 512 * 1024


class ContinuationLinkError(ValueError):
    pass


class ContinuationLinkService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def discover(
        self, owner_id: UUID, asset_id: UUID, work_id: UUID | None, content: bytes
    ) -> int:
        """Persist local FB2 evidence; never raises for malformed optional evidence."""
        try:
            links = extract_continuation_links(content)
        except ValueError:
            return 0
        added = 0
        for link in links:
            exists = await self._session.scalar(
                select(ContinuationLinkCandidateModel.id).where(
                    ContinuationLinkCandidateModel.owner_id == owner_id,
                    ContinuationLinkCandidateModel.source_asset_id == asset_id,
                    ContinuationLinkCandidateModel.url == link.url,
                )
            )
            if exists is not None:
                continue
            self._session.add(
                ContinuationLinkCandidateModel(
                    owner_id=owner_id,
                    source_asset_id=asset_id,
                    source_work_id=work_id,
                    url=link.url,
                    context=link.context,
                )
            )
            added += 1
        return added

    async def list_pending(
        self, owner_id: UUID, limit: int = 50
    ) -> list[ContinuationLinkCandidateModel]:
        return list(
            (
                await self._session.execute(
                    select(ContinuationLinkCandidateModel)
                    .where(
                        ContinuationLinkCandidateModel.owner_id == owner_id,
                        ContinuationLinkCandidateModel.status.in_(
                            ("pending", "resolved", "matched")
                        ),
                    )
                    .order_by(ContinuationLinkCandidateModel.created_at.desc())
                    .limit(limit)
                )
            ).scalars()
        )

    async def resolve_title(
        self, owner_id: UUID, candidate_id: UUID
    ) -> ContinuationLinkCandidateModel | None:
        candidate = await self._session.get(ContinuationLinkCandidateModel, candidate_id)
        if candidate is None or candidate.owner_id != owner_id:
            return None
        try:
            title = await _fetch_public_title(candidate.url)
        except ContinuationLinkError as exc:
            candidate.status = "blocked"
            candidate.error = str(exc)[:500]
            candidate.checked_at = datetime.now(UTC)
            return candidate

        candidate.page_title = title
        candidate.error = None
        candidate.checked_at = datetime.now(UTC)
        matches = list(
            (
                await self._session.execute(
                    select(WorkModel).where(
                        WorkModel.owner_id == owner_id,
                        WorkModel.title_normalized == normalize_title(title),
                    )
                )
            ).scalars()
        )
        if len(matches) == 1:
            candidate.status = "matched"
            candidate.matched_work_id = matches[0].id
        else:
            candidate.status = "resolved"
            candidate.matched_work_id = None
        return candidate

    async def dismiss(self, owner_id: UUID, candidate_id: UUID) -> bool:
        candidate = await self._session.get(ContinuationLinkCandidateModel, candidate_id)
        if candidate is None or candidate.owner_id != owner_id:
            return False
        candidate.status = "dismissed"
        return True


async def _fetch_public_title(url: str) -> str:
    """Fetch one explicit HTTPS page, title metadata only, without redirects.

    A robots.txt denial, private-network destination, redirect, non-HTML answer,
    or parser error stops the manual check.  This is not a crawler: one explicit
    URL produces at most robots.txt plus one page request.
    """
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ContinuationLinkError("only HTTPS links can be checked")
    await _ensure_public_host(parsed.hostname)
    try:
        async with httpx.AsyncClient(
            timeout=10.0,
            follow_redirects=False,
            headers={
                "Accept": "text/html,application/xhtml+xml",
                "User-Agent": "ghostcar-library/0.1 (personal link review)",
            },
        ) as client:
            robots = await client.get(f"https://{parsed.netloc}/robots.txt")
            if robots.is_redirect or robots.status_code not in {200, 404}:
                raise ContinuationLinkError("robots.txt cannot be checked")
            if _robots_disallow(robots.text, parsed.path or "/"):
                raise ContinuationLinkError("robots.txt disallows this link")
            async with client.stream("GET", url) as response:
                if response.status_code != 200:
                    raise ContinuationLinkError(f"page returned {response.status_code}")
                if not response.headers.get("content-type", "").lower().startswith("text/html"):
                    raise ContinuationLinkError("page is not HTML")
                chunks: list[bytes] = []
                total = 0
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > _MAX_HTML_BYTES:
                        raise ContinuationLinkError("page exceeds title-read limit")
                    chunks.append(chunk)
    except httpx.HTTPError as exc:
        raise ContinuationLinkError(f"page request failed: {exc}") from exc
    try:
        root = html.fromstring(b"".join(chunks))
    except (ValueError, html.etree.ParserError) as exc:
        raise ContinuationLinkError("page HTML cannot be parsed") from exc
    og_values = cast(list[object], root.xpath("//meta[@property='og:title']/@content"))
    title_values = cast(list[object], root.xpath("//title/text()"))
    og_title = [str(value) for value in og_values]
    titles = og_title or [str(value) for value in title_values]
    title = " ".join(titles[0].split()) if titles else ""
    if not title:
        raise ContinuationLinkError("page has no title")
    return title[:500]


async def _ensure_public_host(hostname: str) -> None:
    """Reject loopback/private/link-local DNS results before an outbound fetch."""
    try:
        values = await __import__("asyncio").to_thread(
            socket.getaddrinfo, hostname, 443, type=socket.SOCK_STREAM
        )
    except socket.gaierror as exc:
        raise ContinuationLinkError("host cannot be resolved") from exc
    addresses = {item[4][0] for item in values}
    if not addresses:
        raise ContinuationLinkError("host cannot be resolved")
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            raise ContinuationLinkError("link points to a non-public host")


def _robots_disallow(content: str, path: str) -> bool:
    """Small conservative parser for User-agent: *; absent/404 robots is allowed."""
    active = False
    rules: list[str] = []
    for raw in content.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = (part.strip() for part in line.split(":", 1))
        key = key.casefold()
        if key == "user-agent":
            active = value.casefold() in {"*", "ghostcar-library"}
        elif active and key == "disallow" and value:
            rules.append(value)
    return any(path.startswith(rule) for rule in rules)

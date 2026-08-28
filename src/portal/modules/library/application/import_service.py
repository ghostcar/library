"""Import application service (master prompt 6).

Pipeline per file: quarantine → format detection (content) → sha256 →
duplicate check → original asset → deterministic match → events.
Duplicates are recorded as candidates, never silently dropped or merged.
ZIP archives containing FB2/EPUB books are expanded before processing.
"""

from __future__ import annotations

import io
import logging
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from portal.core.events.repository import OutboxRepository
from portal.core.storage.local import LocalStorageAdapter, StorageError
from portal.modules.library.application.filename_parser import ParsedFilename, parse_filename
from portal.modules.library.application.services import CatalogService, RegisterWorkInput
from portal.modules.library.domain import entities as de
from portal.modules.library.domain import import_entities as ie
from portal.modules.library.domain.enums import AssetFormat, AssetKind
from portal.modules.library.domain.value_objects import Sha256
from portal.modules.library.infrastructure.format_detection import (
    UnknownFormatError,
    detect_format,
)
from portal.modules.library.infrastructure.import_repositories import (
    DuplicateCandidateRepository,
    ImportBatchRepository,
    ImportItemRepository,
)
from portal.modules.library.infrastructure.repositories import (
    AssetRepository,
    AuthorRepository,
    SeriesRepository,
    WorkRepository,
)

logger = logging.getLogger("library.import")

_MAX_QUARANTINE_NAME = 128
_MAX_ARCHIVE_ENTRIES = 100
_MAX_ARCHIVE_ENTRY_BYTES = 200 * 1024 * 1024  # 200 MiB per entry
_MAX_ARCHIVE_TOTAL_BYTES = 500 * 1024 * 1024  # 500 MiB total uncompressed
_BOOK_EXTENSIONS = frozenset({".fb2", ".epub"})


def expand_book_archive(
    filename: str,
    content: bytes,
    *,
    max_entries: int = _MAX_ARCHIVE_ENTRIES,
    max_entry_bytes: int = _MAX_ARCHIVE_ENTRY_BYTES,
    max_total_bytes: int = _MAX_ARCHIVE_TOTAL_BYTES,
) -> list[tuple[str, bytes]] | None:
    """Expand a ZIP archive into individual book files.

    Returns ``None`` if *content* is not a ZIP archive or is an EPUB
    (which is a book itself, not an archive of books).  Returns a list of
    ``(filename, bytes)`` tuples for each FB2/EPUB found inside the ZIP.

    Raises ``ValueError`` if the archive is valid but contains no book files
    (caller should create a rejected import item).

    Zip-bomb guards: entry count ≤ *max_entries*, each entry ≤
    *max_entry_bytes*, total uncompressed ≤ *max_total_bytes*.
    """
    if not zipfile.is_zipfile(io.BytesIO(content)):
        return None

    # EPUB is a book itself — don't expand it.  An EPUB ZIP always contains
    # a "mimetype" entry whose content is "application/epub+zip".
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            if "mimetype" in zf.namelist():
                mt = zf.read("mimetype").decode("ascii", errors="ignore").strip()
                if mt == "application/epub+zip":
                    return None
    except (zipfile.BadZipFile, OSError):
        return None

    entries: list[tuple[str, bytes]] = []
    total_bytes = 0
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                basename = Path(info.filename).name
                if basename.startswith(".") or basename.startswith("__MACOSX"):
                    continue
                if Path(basename).suffix.lower() not in _BOOK_EXTENSIONS:
                    continue
                if len(entries) >= max_entries:
                    raise ValueError(f"archive contains more than {max_entries} book files")
                if info.file_size > max_entry_bytes:
                    msg = f"entry {basename} is {info.file_size} bytes (limit {max_entry_bytes})"
                    raise ValueError(msg)
                total_bytes += info.file_size
                if total_bytes > max_total_bytes:
                    raise ValueError(f"total uncompressed size exceeds {max_total_bytes} bytes")
                entries.append((basename, zf.read(info.filename)))
    except (zipfile.BadZipFile, OSError) as exc:
        raise ValueError(f"corrupt archive: {exc}") from exc

    if not entries:
        raise ValueError("archive contains no FB2/EPUB book files")
    return entries


@dataclass(slots=True)
class ScanEntry:
    path: Path
    size_bytes: int
    sha256: str
    verdict: str  # new | duplicate
    existing_asset_id: UUID | None


class ImportService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        storage: LocalStorageAdapter,
        max_file_bytes: int,
        max_files_per_batch: int,
    ) -> None:
        self._session_factory = session_factory
        self._storage = storage
        self._max_file_bytes = max_file_bytes
        self._max_files = max_files_per_batch

    # --- upload ---------------------------------------------------------

    async def import_uploads(
        self,
        owner_id: UUID,
        uploads: list[tuple[str, bytes]],
        *,
        source: ie.ImportSource = ie.ImportSource.UPLOAD,
    ) -> ie.ImportBatch:
        """Process manually uploaded files (master prompt 6.1.1).

        ZIP archives (non-EPUB) are expanded first: each FB2/EPUB inside
        becomes a separate import item.  Archives with no books are rejected.
        """
        # --- phase 1: expand ZIP archives ---------------------------------
        expanded: list[tuple[str, bytes]] = []
        pre_rejected: list[tuple[str, str]] = []

        for filename, content in uploads:
            try:
                entries = expand_book_archive(filename, content)
            except ValueError as exc:
                pre_rejected.append((_safe_name(filename), str(exc)))
                continue

            if entries is None:
                # Not a ZIP or is EPUB → pass through as-is.
                expanded.append((filename, content))
            else:
                expanded.extend(entries)

        if len(expanded) + len(pre_rejected) > self._max_files:
            msg = f"too many files in one batch (max {self._max_files})"
            raise ValueError(msg)

        # --- phase 2: create batch and process ----------------------------
        async with self._session_factory() as session, session.begin():
            batch_repo = ImportBatchRepository(session)
            batch = await batch_repo.add(
                ie.ImportBatch(owner_id=owner_id, source=source),
            )
        batch.mark_running()

        failed = 0

        # Reject archives that contained no book files.
        for safe_name, reason in pre_rejected:
            async with self._session_factory() as session, session.begin():
                items = ImportItemRepository(session)
                item = await items.add(
                    ie.ImportItem(
                        batch_id=batch.id,
                        owner_id=owner_id,
                        filename=safe_name,
                    ),
                )
                item.reject(reason)
                await items.update(item)
            failed += 1

        for filename, content in expanded:
            try:
                await self._process_one(owner_id, batch.id, filename, content)
            except Exception:
                logger.exception("import of %s failed", filename)
                failed += 1

        batch.finish(failed_items=failed)

        async with self._session_factory() as session, session.begin():
            await ImportBatchRepository(session).update_status(batch)
        return batch

    async def _process_one(
        self,
        owner_id: UUID,
        batch_id: UUID,
        filename: str,
        content: bytes,
    ) -> ie.ImportItem:
        async with self._session_factory() as session, session.begin():
            items = ImportItemRepository(session)
            item = await items.add(
                ie.ImportItem(
                    batch_id=batch_id,
                    owner_id=owner_id,
                    filename=_safe_name(filename),
                ),
            )
            item.size_bytes = len(content)

            # 1. quarantine first (master prompt 6.3)
            quarantine_path = await self._quarantine(batch_id, filename, content)
            item.status = ie.ItemStatus.QUARANTINED
            await items.update(item)

            # 2. format detection by content
            try:
                info = detect_format(content)
            except UnknownFormatError as exc:
                item.reject(str(exc))
                await items.update(item)
                await self._discard_quarantine(quarantine_path)
                return item
            item.detected_format = info.format.value
            item.sha256 = Sha256(_sha256_hex(content))

            # 3. exact-content duplicate check
            assets = AssetRepository(session)
            existing = await assets.get_by_sha256(owner_id, item.sha256)
            if existing is not None:
                item.status = ie.ItemStatus.DUPLICATE
                item.asset_id = existing.id
                item.work_id = existing.work_id
                item.match_evidence = {
                    "reason": "exact_content",
                    "existing_asset": str(existing.id),
                }
                await items.update(item)
                await self._discard_quarantine(quarantine_path)
                await self._emit(
                    session,
                    owner_id,
                    "DuplicateSuspected",
                    {
                        "asset_id": str(existing.id),
                        "reason": "exact_content",
                    },
                )
                return item

            # 4. store original (content-addressed, immutable)
            extension = info.format.value
            try:
                stored = await self._storage.save("originals", content, extension)
            except StorageError as exc:
                item.fail(f"storage error: {exc}")
                await items.update(item)
                await self._discard_quarantine(quarantine_path)
                return item

            # 5. deterministic match by filename
            parsed = parse_filename(filename)
            work_id, evidence = await self._match_or_create(session, owner_id, parsed)

            asset = await assets.add(
                de.Asset(
                    owner_id=owner_id,
                    sha256=item.sha256,
                    format=AssetFormat(info.format.value),
                    kind=AssetKind.ORIGINAL,
                    size_bytes=len(content),
                    storage_path=stored.storage_path,
                    original_filename=_safe_name(filename),
                    work_id=work_id,
                ),
            )

            if info.format is AssetFormat.FB2:
                from portal.modules.library.application.continuation_link_service import (
                    ContinuationLinkService,
                )

                await ContinuationLinkService(session).discover(
                    owner_id, asset.id, work_id, content
                )

            # same work+format with different content → duplicate candidate (§2.3)
            if work_id is not None:
                sibling = await assets.find_by_work_and_format(
                    owner_id,
                    work_id,
                    AssetFormat(info.format.value),
                )
                if sibling is not None and sibling.sha256 != asset.sha256:
                    await DuplicateCandidateRepository(session).add(
                        ie.DuplicateCandidate(
                            owner_id=owner_id,
                            asset_id=asset.id,
                            suspected_of_asset_id=sibling.id,
                            reason=ie.DuplicateReason.SAME_WORK_FORMAT,
                        ),
                    )

            item.asset_id = asset.id
            item.work_id = work_id
            item.status = (
                ie.ItemStatus.MATCHED if work_id is not None else ie.ItemStatus.STORED_UNMATCHED
            )
            item.match_evidence = evidence
            await items.update(item)
            await self._discard_quarantine(quarantine_path)

            await self._emit(
                session,
                owner_id,
                "BookFileImported",
                {
                    "asset_id": str(asset.id),
                    "work_id": str(work_id) if work_id else None,
                    "filename": _safe_name(filename),
                },
            )
            if work_id is not None:
                await self._emit(
                    session,
                    owner_id,
                    "WorkMatched",
                    {
                        "asset_id": str(asset.id),
                        "work_id": str(work_id),
                        "evidence": evidence,
                    },
                )
            return item

    # --- local directories (master prompt 6.1.2, dry-run first) ---------

    async def scan_directories(
        self,
        owner_id: UUID,
        roots: list[Path],
        *,
        known_hashes: dict[str, UUID],
        min_age_seconds: int = 0,
    ) -> list[ScanEntry]:
        """Dry-run: list files with verdicts; no writes."""
        entries: list[ScanEntry] = []
        seen_hashes: set[str] = set()
        for root in roots:
            if not root.is_dir():
                continue
            for path in sorted(root.rglob("*")):
                if not path.is_file() or path.suffix.lower() not in {".fb2", ".epub", ".zip"}:
                    continue
                stat = path.stat()
                if time.time() - stat.st_mtime < min_age_seconds:
                    continue
                size = stat.st_size
                if size > self._max_file_bytes:
                    continue
                digest = _sha256_file(path)
                if digest in known_hashes or digest in seen_hashes:
                    verdict = "duplicate"
                    existing = known_hashes.get(digest)
                else:
                    verdict = "new"
                    existing = None
                    seen_hashes.add(digest)
                entries.append(
                    ScanEntry(path, size, digest, verdict, existing),
                )
        return entries

    async def import_from_scan(
        self,
        owner_id: UUID,
        entries: list[ScanEntry],
        *,
        source: ie.ImportSource = ie.ImportSource.LOCAL_DIR,
    ) -> ie.ImportBatch:
        """Apply a scan: only 'new' verdicts are imported."""
        fresh = [e for e in entries if e.verdict == "new"]
        uploads: list[tuple[str, bytes]] = [
            (entry.path.name, entry.path.read_bytes()) for entry in fresh
        ]
        return await self.import_uploads(owner_id, uploads, source=source)

    # --- matching --------------------------------------------------------

    async def _match_or_create(
        self,
        session: AsyncSession,
        owner_id: UUID,
        parsed: ParsedFilename,
    ) -> tuple[UUID | None, dict[str, Any]]:
        """Deterministic policy (master prompt 8.5):
        well-formed filename (author+title) → create/reuse canon entities;
        otherwise leave unmatched for review. Evidence is always recorded.
        """
        evidence: dict[str, Any] = {
            "parser": "deterministic-v1",
            "parsed": {
                "author": parsed.author,
                "series": parsed.series,
                "series_index": str(parsed.series_index) if parsed.series_index else None,
                "title": parsed.title,
            },
        }
        if not parsed.is_well_formed:
            return None, evidence

        catalog = CatalogService(
            works=WorkRepository(session),
            authors=AuthorRepository(session),
            series=SeriesRepository(session),
        )
        work = await catalog.register_work(
            RegisterWorkInput(
                owner_id=owner_id,
                title=parsed.title,
                author_names=[parsed.author] if parsed.author else [],
                series_title=parsed.series,
                series_index_raw=str(parsed.series_index) if parsed.series_index else None,
            ),
        )
        evidence["work_id"] = str(work.id)
        evidence["decision"] = "auto_applied_well_formed_filename"
        return work.id, evidence

    # --- quarantine helpers ------------------------------------------------

    async def _quarantine(self, batch_id: UUID, filename: str, content: bytes) -> str:
        safe = _safe_name(filename)[:_MAX_QUARANTINE_NAME]
        relative = f"quarantine/{batch_id}/{safe}"
        await self._storage.save_raw("quarantine", f"{batch_id}/{safe}", content)
        return relative

    async def _discard_quarantine(self, relative: str) -> None:
        try:
            await self._storage.remove(relative)
        except StorageError:
            logger.warning("could not remove quarantine object %s", relative)

    async def _emit(
        self,
        session: AsyncSession,
        owner_id: UUID,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        envelope = {"owner_id": str(owner_id), **payload}
        await OutboxRepository(session).enqueue(event_type, envelope)


def _sha256_hex(content: bytes) -> str:
    import hashlib

    return hashlib.sha256(content).hexdigest()


def _sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_name(filename: str) -> str:
    """Strip any path component (uploads are untrusted, master prompt 6.3)."""
    name = Path(filename).name
    return name or "unnamed"

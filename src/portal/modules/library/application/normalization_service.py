"""Normalization service: pipeline (7.2), manifest (7.7), idempotence, invariants."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from portal.core.events.repository import OutboxRepository
from portal.core.storage.local import LocalStorageAdapter
from portal.modules.library.domain import entities as de
from portal.modules.library.domain import normalization as nz
from portal.modules.library.domain.enums import AssetFormat, AssetKind, AssetRelationType
from portal.modules.library.domain.value_objects import Sha256
from portal.modules.library.infrastructure.normalization_orm import NormalizationRunModel
from portal.modules.library.infrastructure.normalizer import epub as epub_mod
from portal.modules.library.infrastructure.normalizer import fb2 as fb2_mod
from portal.modules.library.infrastructure.normalizer.fingerprints import compute_fingerprints
from portal.modules.library.infrastructure.repositories import AssetRepository


class NormalizationError(Exception):
    pass


class AssetNotFoundError(NormalizationError):
    pass


class UnsupportedFormatError(NormalizationError):
    pass


@dataclass(slots=True)
class RunResult:
    run_id: UUID
    state: nz.RunState
    derivative_asset_id: UUID | None
    needs_review: bool
    idempotent: bool = False


class NormalizationService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        storage: LocalStorageAdapter,
    ) -> None:
        self._session_factory = session_factory
        self._storage = storage

    # --- public API -------------------------------------------------------

    async def request_normalization(
        self,
        owner_id: UUID,
        asset_id: UUID,
        profile_name: nz.ProfileName = nz.DEFAULT_PROFILE,
    ) -> RunResult:
        """Idempotent: returns the existing completed run for the same input+profile."""
        profile = nz.PROFILES[profile_name]
        async with self._session_factory() as session, session.begin():
            assets = AssetRepository(session)
            asset = await assets.get(owner_id, asset_id)
            if asset is None:
                raise AssetNotFoundError(str(asset_id))
            if asset.kind is not AssetKind.ORIGINAL:
                msg = "only original assets can be normalized"
                raise NormalizationError(msg)

            existing = await self._find_completed_run(
                session,
                owner_id,
                asset_id,
                profile,
            )
            if existing is not None:
                return RunResult(
                    run_id=existing.id,
                    state=nz.RunState(existing.state),
                    derivative_asset_id=existing.derivative_asset_id,
                    needs_review=existing.needs_review,
                    idempotent=True,
                )

            run = nz.NormalizationRun(
                owner_id=owner_id,
                input_asset_id=asset_id,
                profile=profile.name,
                profile_version=profile.version,
                normalizer_version=nz.NORMALIZER_VERSION,
                input_sha256=asset.sha256,
            )
            session.add(
                NormalizationRunModel(
                    id=run.id,
                    owner_id=run.owner_id,
                    input_asset_id=run.input_asset_id,
                    input_sha256=run.input_sha256.value if run.input_sha256 else None,
                    profile=run.profile.value,
                    profile_version=run.profile_version,
                    normalizer_version=run.normalizer_version,
                    state=run.state.value,
                    created_at=run.created_at,
                ),
            )
            await session.flush()
            return RunResult(
                run_id=run.id,
                state=run.state,
                derivative_asset_id=None,
                needs_review=False,
            )

    async def execute_run(self, owner_id: UUID, run_id: UUID) -> RunResult:
        """Executed by the worker. Loads the run, transforms, verifies, stores.

        A failed transform is committed as run.state=failed (the failure record
        must survive); the error is raised only after the transaction commits.
        """
        started = time.monotonic()
        failure: str | None = None
        run_result: RunResult | None = None

        async with self._session_factory() as session, session.begin():
            run_row = await session.get(NormalizationRunModel, run_id)
            if run_row is None or run_row.owner_id != owner_id:
                raise AssetNotFoundError(str(run_id))
            if run_row.state not in {nz.RunState.RECEIVED.value, nz.RunState.FAILED.value}:
                return RunResult(
                    run_id=run_row.id,
                    state=nz.RunState(run_row.state),
                    derivative_asset_id=run_row.derivative_asset_id,
                    needs_review=run_row.needs_review,
                    idempotent=True,
                )

            assets = AssetRepository(session)
            asset = await assets.get(owner_id, run_row.input_asset_id)
            if asset is None:
                msg = f"input asset {run_row.input_asset_id} not found"
                raise AssetNotFoundError(msg)
            profile = nz.PROFILES[nz.ProfileName(run_row.profile)]

            content = await self._storage.open(asset.storage_path)

            result: TransformResult | None = None
            try:
                if asset.format is AssetFormat.FB2:
                    result = self._run_fb2(content, profile)
                elif asset.format is AssetFormat.EPUB:
                    result = self._run_epub(content, profile)
                else:
                    msg = f"unsupported format {asset.format}"
                    raise UnsupportedFormatError(msg)
            except Exception as exc:
                failure = str(exc)[:2000]
                run_row.state = nz.RunState.FAILED.value
                run_row.error = failure
                run_row.completed_at = _utcnow()

            if result is not None:
                derivative_asset = await self._store_derivative(
                    session,
                    owner_id,
                    asset,
                    result,
                )
                duration = round(time.monotonic() - started, 3)

                run_row.derivative_asset_id = derivative_asset.id
                run_row.output_sha256 = derivative_asset.sha256.value
                run_row.actions = _append_action(
                    [a.to_dict() for a in result.actions],
                    "parse",
                    {"bytes": len(content)},
                )
                run_row.manifest = {
                    **result.manifest,
                    "duration_seconds": duration,
                    "input_asset_id": str(asset.id),
                    "derivative_asset_id": str(derivative_asset.id),
                    "fingerprints_version": 1,
                }
                if result.needs_review:
                    run_row.state = nz.RunState.NEEDS_REVIEW.value
                    run_row.needs_review = True
                    run_row.review_reason = result.review_reason
                else:
                    run_row.state = nz.RunState.DERIVATIVE_READY.value
                run_row.completed_at = _utcnow()

                run_result = RunResult(
                    run_id=run_row.id,
                    state=nz.RunState(run_row.state),
                    derivative_asset_id=derivative_asset.id,
                    needs_review=run_row.needs_review,
                )
                await self._emit(
                    owner_id,
                    "NormalizationCompleted",
                    {
                        "run_id": str(run_row.id),
                        "input_asset_id": str(asset.id),
                        "derivative_asset_id": str(derivative_asset.id),
                    },
                )

        if failure is not None:
            await self._emit_failure(owner_id, run_id, failure)
            raise NormalizationError(failure)
        assert run_result is not None
        return run_result

    async def prefer_derivative(self, owner_id: UUID, run_id: UUID) -> bool:
        """Mark the run's derivative as the preferred file for its work."""
        async with self._session_factory() as session, session.begin():
            run_row = await session.get(NormalizationRunModel, run_id)
            if run_row is None or run_row.owner_id != owner_id:
                return False
            if run_row.derivative_asset_id is None:
                return False
            derivative = await AssetRepository(session).get(owner_id, run_row.derivative_asset_id)
            if derivative is None:
                return False

            await AssetRepository(session).set_preferred(owner_id, derivative.id)
            if run_row.state == nz.RunState.DERIVATIVE_READY.value:
                run_row.state = nz.RunState.PREFERRED.value
            await self._emit(
                owner_id,
                "NormalizationCompleted",
                {
                    "run_id": str(run_id),
                    "preferred_asset_id": str(derivative.id),
                },
            )
            return True

    # --- internals ---------------------------------------------------------

    def _run_fb2(self, content: bytes, profile: nz.Profile) -> TransformResult:
        root = fb2_mod.parse_fb2(content)
        images = fb2_mod.fb2_images(root)
        chapters = fb2_mod.fb2_chapters_text(root)
        before = compute_fingerprints(root, chapters, images)

        serialized, actions, cover_info = fb2_mod.transform_fb2(root, profile)
        new_root = fb2_mod.parse_fb2(serialized)
        kept_cover_href = cover_info.get("href")
        new_images = [img for img in fb2_mod.fb2_images(new_root) if img["href"] == kept_cover_href]
        new_chapters = fb2_mod.fb2_chapters_text(new_root)
        after = compute_fingerprints(new_root, new_chapters, new_images)

        invariant_ok = before.visible_text == after.visible_text
        actions.append(
            nz.RunAction(
                nz.ActionKind.VERIFY_TEXT_INVARIANT,
                {
                    "ok": invariant_ok,
                    "before": before.visible_text[:16],
                    "after": after.visible_text[:16],
                },
            ),
        )
        if profile.strict_text_fingerprint and not invariant_ok:
            msg = "text invariant violated: visible-text fingerprint changed"
            raise NormalizationError(msg)

        manifest = {
            "profile": profile.name.value,
            "profile_version": profile.version,
            "normalizer_version": nz.NORMALIZER_VERSION,
            "format": AssetFormat.FB2.value,
            "actions": [a.to_dict() for a in actions],
            "fingerprints": {
                "before": {
                    "visible_text": before.visible_text,
                    "structure": before.structure,
                    "images": before.images,
                    "chapters": before.chapters,
                },
                "after": {
                    "visible_text": after.visible_text,
                    "structure": after.structure,
                    "images": after.images,
                    "chapters": after.chapters,
                },
                "text_invariant_ok": invariant_ok,
            },
            "cover": cover_info,
            "warnings": [],
        }
        review_reason = None
        if cover_info.get("status") == "review":
            review_reason = f"cover: {cover_info.get('reason')}"
        return TransformResult(
            serialized=serialized,
            actions=actions,
            manifest=manifest,
            needs_review=review_reason is not None,
            review_reason=review_reason,
            derivative_extension="fb2",
        )

    def _run_epub(self, content: bytes, profile: nz.Profile) -> TransformResult:
        book = epub_mod.parse_epub(content)
        images = epub_mod.epub_images(book)
        chapters = epub_mod.epub_chapter_texts(book)
        before_text = epub_mod.epub_visible_text(book)

        serialized, actions, cover_info = epub_mod.transform_epub(book, profile)

        new_book = epub_mod.parse_epub(serialized)
        after_text = epub_mod.epub_visible_text(new_book)
        new_images = epub_mod.epub_images(new_book)

        import hashlib

        before_text_hash = hashlib.sha256(before_text.encode()).hexdigest()
        after_text_hash = hashlib.sha256(after_text.encode()).hexdigest()
        invariant_ok = before_text_hash == after_text_hash
        actions.append(
            nz.RunAction(
                nz.ActionKind.VERIFY_TEXT_INVARIANT,
                {"ok": invariant_ok},
            ),
        )
        if profile.strict_text_fingerprint and not invariant_ok:
            msg = "text invariant violated: EPUB visible text changed"
            raise NormalizationError(msg)

        manifest = {
            "profile": profile.name.value,
            "profile_version": profile.version,
            "normalizer_version": nz.NORMALIZER_VERSION,
            "format": AssetFormat.EPUB.value,
            "actions": [a.to_dict() for a in actions],
            "fingerprints": {
                "before": {
                    "visible_text": before_text_hash,
                    "images": _images_hash(images),
                    "chapters": [hashlib.sha256(c.encode()).hexdigest() for c in chapters],
                },
                "after": {"visible_text": after_text_hash, "images": _images_hash(new_images)},
                "text_invariant_ok": invariant_ok,
            },
            "cover": cover_info,
            "warnings": ["EPUBCheck not available; structural validation skipped"],
        }
        review_reason = None
        if cover_info.get("status") == "review":
            review_reason = f"cover: {cover_info.get('reason')}"
        return TransformResult(
            serialized=serialized,
            actions=actions,
            manifest=manifest,
            needs_review=review_reason is not None,
            review_reason=review_reason,
            derivative_extension="epub",
        )

    async def _store_derivative(
        self,
        session: AsyncSession,
        owner_id: UUID,
        original: de.Asset,
        result: TransformResult,
    ) -> de.Asset:
        stored = await self._storage.save(
            "derivatives",
            result.serialized,
            result.derivative_extension,
        )
        assets = AssetRepository(session)
        derivative = await assets.add(
            de.Asset(
                owner_id=owner_id,
                sha256=Sha256(_sha_hex(result.serialized)),
                format=original.format,
                kind=AssetKind.NORMALIZED,
                size_bytes=len(result.serialized),
                storage_path=stored.storage_path,
                original_filename=original.original_filename,
                work_id=original.work_id,
            ),
        )
        await assets.add_relation(
            de.AssetRelation(
                owner_id=owner_id,
                asset_id=derivative.id,
                related_asset_id=original.id,
                relation_type=AssetRelationType.NORMALIZED,
            ),
        )
        return derivative

    async def _find_completed_run(
        self,
        session: AsyncSession,
        owner_id: UUID,
        asset_id: UUID,
        profile: nz.Profile,
    ) -> NormalizationRunModel | None:
        """Any live run (queued/running/done/review) for this input+profile.

        Failed runs are excluded: they don't occupy the idempotence slot
        and a new request may retry them with a fresh run.
        """
        stmt = (
            select(NormalizationRunModel)
            .where(
                NormalizationRunModel.owner_id == owner_id,
                NormalizationRunModel.input_asset_id == asset_id,
                NormalizationRunModel.profile == profile.name.value,
                NormalizationRunModel.profile_version == profile.version,
                NormalizationRunModel.normalizer_version == nz.NORMALIZER_VERSION,
                NormalizationRunModel.state.notin_([nz.RunState.FAILED.value]),
            )
            .order_by(NormalizationRunModel.created_at.desc())
            .limit(1)
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def get_run(self, owner_id: UUID, run_id: UUID) -> dict[str, Any] | None:
        async with self._session_factory() as session:
            run_row = await session.get(NormalizationRunModel, run_id)
            if run_row is None or run_row.owner_id != owner_id:
                return None
            return {
                "id": run_row.id,
                "input_asset_id": run_row.input_asset_id,
                "derivative_asset_id": run_row.derivative_asset_id,
                "profile": run_row.profile,
                "state": run_row.state,
                "needs_review": run_row.needs_review,
                "review_reason": run_row.review_reason,
                "manifest": run_row.manifest,
                "error": run_row.error,
                "created_at": run_row.created_at,
                "completed_at": run_row.completed_at,
            }

    async def list_runs(self, owner_id: UUID, limit: int = 50) -> list[dict[str, Any]]:
        async with self._session_factory() as session:
            stmt = (
                select(NormalizationRunModel)
                .where(NormalizationRunModel.owner_id == owner_id)
                .order_by(NormalizationRunModel.created_at.desc())
                .limit(limit)
            )
            rows = (await session.execute(stmt)).scalars().all()
            return [
                {
                    "id": r.id,
                    "input_asset_id": r.input_asset_id,
                    "derivative_asset_id": r.derivative_asset_id,
                    "profile": r.profile,
                    "state": r.state,
                    "needs_review": r.needs_review,
                    "review_reason": r.review_reason,
                    "created_at": r.created_at,
                    "completed_at": r.completed_at,
                }
                for r in rows
            ]

    async def _emit_failure(self, owner_id: UUID, run_id: UUID, reason: str) -> None:
        """NormalizationFailed event in its own transaction (survives rollback)."""
        async with self._session_factory() as session, session.begin():
            envelope = {
                "owner_id": str(owner_id),
                "run_id": str(run_id),
                "reason": reason,
            }
            await OutboxRepository(session).enqueue("NormalizationFailed", envelope)

    async def _emit(self, owner_id: UUID, event_type: str, payload: dict[str, Any]) -> None:
        async with self._session_factory() as session, session.begin():
            envelope = {"owner_id": str(owner_id), **payload}
            await OutboxRepository(session).enqueue(event_type, envelope)


@dataclass(slots=True)
class TransformResult:
    serialized: bytes
    actions: list[nz.RunAction]
    manifest: dict[str, Any]
    needs_review: bool
    review_reason: str | None
    derivative_extension: str


def _append_action(
    actions: list[dict[str, Any]],
    kind: str,
    detail: dict[str, Any],
) -> list[dict[str, Any]]:
    from datetime import UTC, datetime

    return [*actions, {"kind": kind, "detail": detail, "at": datetime.now(UTC).isoformat()}]


def _utcnow() -> datetime:
    from datetime import UTC, datetime

    return datetime.now(UTC)


def _sha_hex(content: bytes) -> str:
    import hashlib

    return hashlib.sha256(content).hexdigest()


def _images_hash(images: list[dict[str, Any]]) -> str:
    from portal.modules.library.infrastructure.normalizer.fingerprints import (
        image_manifest_fingerprint,
    )

    return image_manifest_fingerprint(images)

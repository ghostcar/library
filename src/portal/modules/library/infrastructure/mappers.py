"""Mapping between domain entities and ORM models."""

from __future__ import annotations

from portal.modules.library.domain import entities as de
from portal.modules.library.domain.enums import (
    AssetFormat,
    AssetKind,
    MembershipType,
    ReadingChangeSource,
    ReadingStatus,
    WorkAuthorRole,
)
from portal.modules.library.domain.value_objects import SeriesIndex, Sha256
from portal.modules.library.infrastructure import orm


def author_to_domain(m: orm.AuthorModel) -> de.Author:
    return de.Author(
        owner_id=m.owner_id,
        name=m.name,
        sort_name=m.sort_name,
        id=m.id,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def work_to_domain(
    m: orm.WorkModel,
    author_rows: list[orm.WorkAuthorModel] | None = None,
) -> de.Work:
    work = de.Work(
        owner_id=m.owner_id,
        title=m.title,
        language=m.language,
        description=m.description,
        id=m.id,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )
    for row in author_rows or []:
        work.authors.append(
            de.WorkAuthor(
                author_id=row.author_id,
                role=WorkAuthorRole(row.role),
                position=row.position,
            ),
        )
    return work


def series_to_domain(m: orm.SeriesModel) -> de.Series:
    return de.Series(
        owner_id=m.owner_id,
        title=m.title,
        description=m.description,
        id=m.id,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def membership_to_domain(m: orm.SeriesMembershipModel) -> de.SeriesMembership:
    return de.SeriesMembership(
        owner_id=m.owner_id,
        series_id=m.series_id,
        work_id=m.work_id,
        index=SeriesIndex(raw=m.index_raw, sort_key=m.index_sort),
        membership_type=MembershipType(m.membership_type),
        id=m.id,
    )


def source_record_to_domain(m: orm.SourceRecordModel) -> de.SourceRecord:
    return de.SourceRecord(
        owner_id=m.owner_id,
        adapter_id=m.adapter_id,
        external_id=m.external_id,
        work_id=m.work_id,
        url=m.url,
        raw_metadata=dict(m.raw_metadata or {}),
        parser_version=m.parser_version,
        last_observed_at=m.last_observed_at,
        id=m.id,
        created_at=m.created_at,
    )


def asset_to_domain(m: orm.AssetModel) -> de.Asset:
    return de.Asset(
        owner_id=m.owner_id,
        sha256=Sha256(m.sha256),
        format=AssetFormat(m.format),
        kind=AssetKind(m.kind),
        size_bytes=m.size_bytes,
        storage_path=m.storage_path,
        original_filename=m.original_filename,
        id=m.id,
        created_at=m.created_at,
    )


def reading_state_to_domain(m: orm.ReadingStateModel) -> de.ReadingState:
    return de.ReadingState(
        owner_id=m.owner_id,
        work_id=m.work_id,
        status=ReadingStatus(m.status),
        progress_percent=m.progress_percent,
        change_source=ReadingChangeSource(m.change_source),
        id=m.id,
        changed_at=m.changed_at,
        created_at=m.created_at,
    )


def author_to_orm(e: de.Author) -> orm.AuthorModel:
    return orm.AuthorModel(
        id=e.id,
        owner_id=e.owner_id,
        name=e.name,
        name_normalized=de.normalize_title(e.name),
        sort_name=e.sort_name,
        created_at=e.created_at,
        updated_at=e.updated_at,
    )


def work_to_orm(e: de.Work) -> orm.WorkModel:
    return orm.WorkModel(
        id=e.id,
        owner_id=e.owner_id,
        title=e.title,
        title_normalized=e.title_normalized,
        language=e.language,
        description=e.description,
        created_at=e.created_at,
        updated_at=e.updated_at,
    )


def work_authors_to_orm(e: de.Work) -> list[orm.WorkAuthorModel]:
    return [
        orm.WorkAuthorModel(
            owner_id=e.owner_id,
            work_id=e.id,
            author_id=wa.author_id,
            role=wa.role.value,
            position=wa.position,
        )
        for wa in e.authors
    ]


def series_to_orm(e: de.Series) -> orm.SeriesModel:
    return orm.SeriesModel(
        id=e.id,
        owner_id=e.owner_id,
        title=e.title,
        title_normalized=e.title_normalized,
        description=e.description,
        created_at=e.created_at,
        updated_at=e.updated_at,
    )


def membership_to_orm(e: de.SeriesMembership) -> orm.SeriesMembershipModel:
    return orm.SeriesMembershipModel(
        id=e.id,
        owner_id=e.owner_id,
        series_id=e.series_id,
        work_id=e.work_id,
        index_raw=e.index.raw,
        index_sort=e.index.sort_key,
        membership_type=e.membership_type.value,
    )


def source_record_to_orm(e: de.SourceRecord) -> orm.SourceRecordModel:
    return orm.SourceRecordModel(
        id=e.id,
        owner_id=e.owner_id,
        adapter_id=e.adapter_id,
        external_id=e.external_id,
        work_id=e.work_id,
        url=e.url,
        raw_metadata=e.raw_metadata,
        parser_version=e.parser_version,
        last_observed_at=e.last_observed_at,
        created_at=e.created_at,
    )


def asset_to_orm(e: de.Asset) -> orm.AssetModel:
    return orm.AssetModel(
        id=e.id,
        owner_id=e.owner_id,
        sha256=str(e.sha256),
        format=e.format.value,
        kind=e.kind.value,
        size_bytes=e.size_bytes,
        storage_path=e.storage_path,
        original_filename=e.original_filename,
        created_at=e.created_at,
    )


def reading_state_to_orm(e: de.ReadingState) -> orm.ReadingStateModel:
    return orm.ReadingStateModel(
        id=e.id,
        owner_id=e.owner_id,
        work_id=e.work_id,
        status=e.status.value,
        progress_percent=e.progress_percent,
        change_source=e.change_source.value,
        changed_at=e.changed_at,
        created_at=e.created_at,
    )

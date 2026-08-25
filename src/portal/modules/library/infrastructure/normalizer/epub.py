"""EPUB transformer (master prompt 7.6).

Repacks the ZIP deterministically: mimetype first and stored, rest deflated.
prose_compact keeps exactly one cover image and strips in-document images
while preserving all visible text (captions are text; <img> is not).
"""

from __future__ import annotations

import hashlib
import io
import posixpath
import zipfile
from dataclasses import dataclass, field
from typing import Any

from lxml import etree

from portal.modules.library.domain.normalization import ActionKind, Profile, RunAction
from portal.modules.library.infrastructure.normalizer.cover import optimize_cover
from portal.modules.library.infrastructure.normalizer.fb2 import safe_parser
from portal.modules.library.infrastructure.normalizer.fingerprints import visible_text

_EPUB_MIMETYPE = "application/epub+zip"


class EPUBParseError(ValueError):
    pass


@dataclass(slots=True)
class EPUBDoc:
    href: str
    tree: etree._Element
    content: bytes


@dataclass(slots=True)
class EPUBBook:
    original: dict[str, bytes] = field(default_factory=dict)
    opf_path: str = ""
    opf_tree: etree._Element | None = None
    spine_docs: list[EPUBDoc] = field(default_factory=list)
    cover_href: str | None = None
    cover_ambiguous: bool = False


def parse_epub(content: bytes) -> EPUBBook:
    book = EPUBBook()
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            if archive.testzip() is not None:
                msg = "corrupt EPUB zip"
                raise EPUBParseError(msg)
            for name in archive.namelist():
                book.original[name] = archive.read(name)
    except zipfile.BadZipFile as exc:
        msg = f"invalid EPUB zip: {exc}"
        raise EPUBParseError(msg) from exc

    if book.original.get("mimetype", b"").strip() != _EPUB_MIMETYPE.encode():
        msg = "mimetype entry missing or wrong"
        raise EPUBParseError(msg)

    container = book.original.get("META-INF/container.xml")
    if container is None:
        msg = "META-INF/container.xml missing"
        raise EPUBParseError(msg)
    try:
        container_tree = etree.fromstring(container, parser=safe_parser())
    except etree.XMLSyntaxError as exc:
        msg = f"invalid container.xml: {exc}"
        raise EPUBParseError(msg) from exc
    rootfile = container_tree.find(".//{*}rootfile")
    if rootfile is None or not rootfile.get("full-path"):
        msg = "container.xml has no rootfile"
        raise EPUBParseError(msg)
    book.opf_path = rootfile.get("full-path") or ""

    try:
        book.opf_tree = etree.fromstring(book.original[book.opf_path], parser=safe_parser())
    except (etree.XMLSyntaxError, KeyError) as exc:
        msg = f"invalid OPF: {exc}"
        raise EPUBParseError(msg) from exc

    _resolve_spine(book)
    _resolve_cover(book)
    return book


def _base_dir(opf_path: str) -> str:
    return posixpath.dirname(opf_path)


def _resolve_spine(book: EPUBBook) -> None:
    if book.opf_tree is None:
        return
    manifest: dict[str, str] = {}
    for item in book.opf_tree.iter("{*}item"):
        item_id, href = item.get("id"), item.get("href")
        media_type = item.get("media-type", "")
        if (
            item_id
            and href
            and media_type
            in {
                "application/xhtml+xml",
                "text/html",
            }
        ):
            manifest[item_id] = href

    base = _base_dir(book.opf_path)
    for itemref in book.opf_tree.iter("{*}itemref"):
        idref = itemref.get("idref")
        href = manifest.get(idref or "")
        if not href:
            continue
        full = posixpath.normpath(posixpath.join(base, href)) if base else href
        raw = book.original.get(full)
        if raw is None:
            continue
        try:
            tree = etree.fromstring(raw, parser=safe_parser())
        except etree.XMLSyntaxError:
            continue
        book.spine_docs.append(EPUBDoc(href=full, tree=tree, content=raw))


def _resolve_cover(book: EPUBBook) -> None:
    if book.opf_tree is None:
        return
    base = _base_dir(book.opf_path)
    cover_id: str | None = None

    for meta in book.opf_tree.iter("{*}meta"):
        if meta.get("name") == "cover":
            cover_id = meta.get("content")

    for item in book.opf_tree.iter("{*}item"):
        properties = item.get("properties", "")
        if "cover-image" in properties.split():
            cover_id = item.get("id")

    if cover_id is None:
        return
    for item in book.opf_tree.iter("{*}item"):
        if item.get("id") == cover_id:
            href = item.get("href", "")
            book.cover_href = posixpath.normpath(posixpath.join(base, href)) if base else href
            return


def transform_epub(
    book: EPUBBook,
    profile: Profile,
) -> tuple[bytes, list[RunAction], dict[str, Any]]:
    actions: list[RunAction] = []
    cover_info: dict[str, Any] = {}

    if profile.images_cover_only:
        cover_info = _strip_images(book, profile, actions)
        _remove_orphaned_resources(book, actions)

    serialized = _repack(book)
    return serialized, actions, cover_info


def _strip_images(book: EPUBBook, profile: Profile, actions: list[RunAction]) -> dict[str, Any]:
    removed_refs = 0
    for doc in book.spine_docs:
        for tag in ("img", "image", "svg"):
            for element in list(doc.tree.iter(f"{{*}}{tag}")):
                parent = element.getparent()
                if parent is not None:
                    parent.remove(element)
                    removed_refs += 1
        doc.content = etree.tostring(
            doc.tree,
            xml_declaration=True,
            encoding="UTF-8",
        )
        book.original[doc.href] = doc.content
    actions.append(RunAction(ActionKind.REMOVE_BODY_IMAGES, {"removed_refs": removed_refs}))

    # keep only the cover binary among image resources
    image_exts = {".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp"}
    removed_files: list[str] = []
    for name in list(book.original):
        if name == "mimetype" or name == book.cover_href:
            continue
        if posixpath.splitext(name)[1].lower() in image_exts:
            del book.original[name]
            removed_files.append(name)
    actions.append(
        RunAction(ActionKind.REMOVE_UNUSED_BINARIES, {"removed_files": removed_files}),
    )

    cover_meta: dict[str, Any] = {"status": "ok" if book.cover_href else "absent"}
    if book.cover_href and book.cover_href in book.original and profile.optimize_cover:
        content = book.original[book.cover_href]
        optimized, meta = optimize_cover(content, profile.cover_max_dimension)
        if optimized != content:
            book.original[book.cover_href] = optimized
            actions.append(
                RunAction(ActionKind.OPTIMIZE_COVER, {**meta, "original_size": len(content)}),
            )
        cover_meta["size"] = len(optimized)
    if book.cover_href is None:
        cover_meta = {"status": "review", "reason": "no cover metadata"}
    return cover_meta


def _remove_orphaned_resources(book: EPUBBook, actions: list[RunAction]) -> None:
    """Remove files that are neither the OPF, container, mimetype, nor in the manifest."""
    if book.opf_tree is None:
        return
    referenced: set[str] = {"META-INF/container.xml", "mimetype", book.opf_path}
    for item in book.opf_tree.iter("{*}item"):
        href = item.get("href")
        if href:
            base = _base_dir(book.opf_path)
            full = posixpath.normpath(posixpath.join(base, href)) if base else href
            referenced.add(full)

    orphans = [name for name in book.original if name not in referenced]
    for name in orphans:
        del book.original[name]
    if orphans:
        actions.append(
            RunAction(ActionKind.REMOVE_ORPHANED_RESOURCES, {"removed": orphans}),
        )


def _repack(book: EPUBBook) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        # mimetype must be first and stored (master prompt 7.6)
        archive.writestr(
            zipfile.ZipInfo("mimetype"),
            book.original.get("mimetype", _EPUB_MIMETYPE.encode()),
            compress_type=zipfile.ZIP_STORED,
        )
        for name in sorted(book.original):
            if name == "mimetype":
                continue
            archive.writestr(name, book.original[name], compress_type=zipfile.ZIP_DEFLATED)
    return buffer.getvalue()


def epub_visible_text(book: EPUBBook) -> str:
    return "\n".join(text for doc in book.spine_docs if (text := visible_text(doc.tree)))


def epub_chapter_texts(book: EPUBBook) -> list[str]:
    return [visible_text(doc.tree) for doc in book.spine_docs]


def epub_images(book: EPUBBook) -> list[dict[str, Any]]:
    images: list[dict[str, Any]] = []
    for name, content in book.original.items():
        if posixpath.splitext(name)[1].lower() in {
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".svg",
            ".webp",
        }:
            images.append(
                {
                    "href": name,
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "size": len(content),
                },
            )
    return images

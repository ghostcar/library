"""FB2 transformer (master prompt 7.5).

Safety: lxml parser with entities not resolved, no network, no DTD loading
(master prompt 6.3: XXE prohibition). The literary text is never modified:
only structure, metadata, resources. Every transform records an action;
the text invariant is verified by fingerprints before/after.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from lxml import etree

from portal.modules.library.domain.normalization import ActionKind, Profile, RunAction
from portal.modules.library.infrastructure.normalizer.fingerprints import (
    visible_text,
)

FB2_NS = "http://www.gribuser.ru/xml/fictionbook/2.0"
FB2_NS_10 = "http://www.gribuser.ru/xml/fictionbook/1.0"
_XLINK = "http://www.w3.org/1999/xlink"


class FB2ParseError(ValueError):
    pass


def safe_parser() -> etree.XMLParser:
    """XXE-safe parser: no entity resolution, no network, no DTD."""
    return etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        dtd_validation=False,
        huge_tree=False,
        remove_comments=False,
        remove_pis=False,
    )


def parse_fb2(content: bytes) -> etree._Element:
    try:
        root = etree.fromstring(content, parser=safe_parser())
    except etree.XMLSyntaxError as exc:
        msg = f"invalid FB2 XML: {exc}"
        raise FB2ParseError(msg) from exc
    if _local(root.tag) != "FictionBook":
        msg = "root element is not FictionBook"
        raise FB2ParseError(msg)
    return root


@dataclass(slots=True)
class FB2Analysis:
    cover_href: str | None = None
    cover_ambiguous: bool = False
    body_images: int = 0
    binaries: dict[str, bytes] = field(default_factory=dict)  # id -> content
    chapters_text: list[str] = field(default_factory=list)
    book_title: str | None = None


def _local(tag: object) -> str:
    if not isinstance(tag, str):
        return ""
    return etree.QName(tag).localname if tag.startswith("{") else tag


def _href(element: etree._Element) -> str | None:
    for attr in (f"{{{_XLINK}}}href", "href"):
        value = element.get(attr)
        if value:
            return value.lstrip("#")
    return None


def analyze_fb2(root: etree._Element) -> FB2Analysis:
    analysis = FB2Analysis()

    title_info = root.find(f"{{{FB2_NS}}}description/{{{FB2_NS}}}title-info")
    if title_info is not None:
        book_title = title_info.find(f"{{{FB2_NS}}}book-title")
        if book_title is not None and book_title.text:
            analysis.book_title = book_title.text

    coverpage = root.find(
        f"{{{FB2_NS}}}description/{{{FB2_NS}}}title-info/{{{FB2_NS}}}coverpage",
    )
    if coverpage is not None:
        images = [img for img in coverpage if _local(img.tag) == "image"]
        hrefs = {h for img in images if (h := _href(img))}
        if len(hrefs) == 1:
            analysis.cover_href = hrefs.pop()
        elif len(hrefs) > 1:
            analysis.cover_ambiguous = True

    for binary in root.iter(f"{{{FB2_NS}}}binary"):
        binary_id = binary.get("id")
        if binary_id and binary.text:
            try:
                import base64

                analysis.binaries[binary_id] = base64.b64decode(binary.text)
            except (ValueError, TypeError):
                analysis.binaries[binary_id] = b""

    for image in root.iter(f"{{{FB2_NS}}}image"):
        image_parent = image.getparent()
        parent_is_coverpage = image_parent is not None and _local(image_parent.tag) == "coverpage"
        if not parent_is_coverpage:
            analysis.body_images += 1

    body = root.find(f"{{{FB2_NS}}}body")
    if body is not None:
        analysis.chapters_text = [
            visible_text(section) for section in body if _local(section.tag) == "section"
        ] or [visible_text(body)]

    return analysis


def transform_fb2(
    root: etree._Element,
    profile: Profile,
) -> tuple[bytes, list[RunAction], dict[str, Any]]:
    """Apply profile transforms. Returns (serialized, actions, cover_info).

    Text nodes are never modified; only elements/attributes are touched.
    """
    actions: list[RunAction] = []
    cover_info: dict[str, Any] = {}

    analysis = analyze_fb2(root)

    if profile.images_cover_only:
        removed_binaries = _remove_body_images_and_binaries(root, analysis, actions)
        cover_info = _extract_cover(root, analysis, profile, removed_binaries, actions)

    _normalize_metadata(root, actions)
    _remove_empty_wrappers(root, actions, profile)
    _ensure_section_ids(root, actions)

    if profile.rebuild_toc_when_unambiguous:
        # FB2 TOC is derived from section titles by readers; ensure titles exist
        _ensure_section_titles(root, actions)

    serialized = etree.tostring(
        root,
        xml_declaration=True,
        encoding="UTF-8",
        pretty_print=False,  # never re-format text nodes
    )
    return serialized, actions, cover_info


def _remove_body_images_and_binaries(
    root: etree._Element,
    analysis: FB2Analysis,
    actions: list[RunAction],
) -> set[str]:
    removed_binaries: set[str] = set()
    for image in list(root.iter(f"{{{FB2_NS}}}image")):
        image_parent = image.getparent()
        if image_parent is not None and _local(image_parent.tag) == "coverpage":
            continue
        href = _href(image)
        parent = image.getparent()
        if parent is not None:
            parent.remove(image)
        if href:
            removed_binaries.add(href)

    for binary in list(root.iter(f"{{{FB2_NS}}}binary")):
        binary_id = binary.get("id")
        if binary_id == analysis.cover_href:
            continue
        parent = binary.getparent()
        if parent is not None:
            parent.remove(binary)
        if binary_id:
            removed_binaries.add(binary_id)

    actions.append(
        RunAction(
            ActionKind.REMOVE_BODY_IMAGES,
            {"removed_images": analysis.body_images, "removed_binaries": len(removed_binaries)},
        ),
    )
    return removed_binaries


def _extract_cover(
    root: etree._Element,
    analysis: FB2Analysis,
    profile: Profile,
    removed_binaries: set[str],
    actions: list[RunAction],
) -> dict[str, Any]:
    if analysis.cover_href is None:
        if analysis.cover_ambiguous:
            return {"status": "review", "reason": "multiple coverpage images"}
        return {"status": "review", "reason": "no coverpage"}

    binary = root.find(f"{{{FB2_NS}}}binary[@id='{analysis.cover_href}']")
    if binary is None:
        return {"status": "review", "reason": "coverpage references missing binary"}

    content_type = binary.get("content-type", "image/jpeg")
    content = analysis.binaries.get(analysis.cover_href, b"")
    if profile.optimize_cover and content:
        from portal.modules.library.infrastructure.normalizer.cover import optimize_cover

        optimized, meta = optimize_cover(content, profile.cover_max_dimension)
        if optimized != content:
            import base64

            binary.text = base64.b64encode(optimized).decode("ascii")
            binary.set("content-type", meta["content_type"])
            actions.append(
                RunAction(ActionKind.OPTIMIZE_COVER, {**meta, "original_size": len(content)}),
            )
            content = optimized

    actions.append(
        RunAction(
            ActionKind.REMOVE_UNUSED_BINARIES,
            {"kept_cover": analysis.cover_href, "content_type": content_type},
        ),
    )
    return {
        "status": "ok",
        "href": analysis.cover_href,
        "content_type": content_type,
        "size": len(content),
    }


def _normalize_metadata(root: etree._Element, actions: list[RunAction]) -> None:
    changed: dict[str, Any] = {}

    document_info = root.find(f"{{{FB2_NS}}}description/{{{FB2_NS}}}document-info")
    if document_info is None:
        description = root.find(f"{{{FB2_NS}}}description")
        if description is not None:
            document_info = etree.SubElement(description, f"{{{FB2_NS}}}document-info")
            changed["document_info_created"] = True
    if document_info is not None:
        doc_id = document_info.find(f"{{{FB2_NS}}}id")
        if doc_id is None or not (doc_id.text or "").strip():
            if doc_id is None:
                doc_id = etree.SubElement(document_info, f"{{{FB2_NS}}}id")
            doc_id.text = str(uuid4())
            changed["document_id_generated"] = True

    if changed:
        actions.append(RunAction(ActionKind.NORMALIZE_METADATA, changed))


def _remove_empty_wrappers(
    root: etree._Element,
    actions: list[RunAction],
    profile: Profile,
) -> None:
    """Remove elements that contain no text at all (master prompt 7.4).

    A wrapper is empty when its full text content is whitespace-only
    and it holds no image/cover references.
    """
    removed = 0
    for element in list(root.iter()):
        tag = _local(element.tag)
        if tag not in {"section", "p", "empty-line", "poem", "stanza", "cite", "epigraph"}:
            continue
        parent = element.getparent()
        if parent is None:
            continue
        if _local(parent.tag) == "coverpage":
            continue
        has_text = any((node.text or "").strip() for node in element.iter() if node.text)
        has_image = any(_local(child.tag) == "image" for child in element.iter())
        if not has_text and not has_image and parent is not None:
            parent.remove(element)
            removed += 1
    if removed:
        actions.append(RunAction(ActionKind.REMOVE_EMPTY_WRAPPERS, {"removed": removed}))


def _ensure_section_ids(root: etree._Element, actions: list[RunAction]) -> None:
    body = root.find(f"{{{FB2_NS}}}body")
    if body is None:
        return
    assigned = 0
    seen: set[str] = set()
    for index, section in enumerate(body.iter(f"{{{FB2_NS}}}section")):
        section_id = section.get("id")
        if not section_id or section_id in seen:
            new_id = f"section-{index + 1}"
            while new_id in seen:
                index += 1
                new_id = f"section-{index + 1}"
            section.set("id", new_id)
            seen.add(new_id)
            assigned += 1
        else:
            seen.add(section_id)
    if assigned:
        actions.append(RunAction(ActionKind.NORMALIZE_METADATA, {"section_ids_assigned": assigned}))


def _ensure_section_titles(root: etree._Element, actions: list[RunAction]) -> None:
    body = root.find(f"{{{FB2_NS}}}body")
    if body is None:
        return
    titled = 0
    for index, section in enumerate(body.iter(f"{{{FB2_NS}}}section")):
        title = section.find(f"{{{FB2_NS}}}title")
        if title is None:
            title = etree.Element(f"{{{FB2_NS}}}title")
            section.insert(0, title)
            titled += 1
        if not any((p.text or "").strip() for p in title.iter(f"{{{FB2_NS}}}p")):
            if len(title) == 0:
                p = etree.SubElement(title, f"{{{FB2_NS}}}p")
                p.text = f"Глава {index + 1}"
                titled += 1
    if titled:
        actions.append(RunAction(ActionKind.REBUILD_TOC, {"sections_titled": titled}))


def fb2_chapters_text(root: etree._Element) -> list[str]:
    analysis = analyze_fb2(root)
    return analysis.chapters_text


def fb2_images(root: etree._Element) -> list[dict[str, Any]]:
    images: list[dict[str, Any]] = []
    for binary in root.iter(f"{{{FB2_NS}}}binary"):
        content_type = binary.get("content-type", "")
        if not content_type.startswith("image/"):
            continue
        content = binary.text or ""
        images.append(
            {
                "href": binary.get("id", ""),
                "sha256": hashlib.sha256(content.encode()).hexdigest(),
                "size": len(content),
            },
        )
    return images

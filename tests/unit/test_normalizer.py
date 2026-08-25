"""Unit tests: fingerprints and FB2/EPUB transformers (prose_compact, invariants)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fixtures.books import epub_document, fb2_document
from portal.modules.library.domain.normalization import (
    PROFILES,
    ProfileName,
)
from portal.modules.library.infrastructure.normalizer import epub as epub_mod
from portal.modules.library.infrastructure.normalizer import fb2 as fb2_mod
from portal.modules.library.infrastructure.normalizer.fingerprints import (
    compute_fingerprints,
    visible_text,
)

PROFILE = PROFILES[ProfileName.PROSE_COMPACT]


class TestFingerprints:
    def test_visible_text_collapses_whitespace_only(self) -> None:
        root = fb2_mod.parse_fb2(fb2_document())
        first = visible_text(root)
        # same text with different technical whitespace must produce same hash
        root2 = fb2_mod.parse_fb2(fb2_document().replace(b".  ", b".\n\t "))
        second = visible_text(root2)
        assert first == second

    def test_visible_text_changes_when_words_change(self) -> None:
        root = fb2_mod.parse_fb2(fb2_document())
        before = visible_text(root)
        tampered = fb2_document().replace("Текст главы 1".encode(), "Текст 1".encode())
        root2 = fb2_mod.parse_fb2(tampered)
        assert before != visible_text(root2)

    def test_punctuation_change_is_detected(self) -> None:
        original = fb2_mod.parse_fb2(fb2_document())
        tampered = fb2_document().replace("Текст главы".encode(), "Текст, главы".encode())
        assert visible_text(original) != visible_text(fb2_mod.parse_fb2(tampered))

    def test_compute_fingerprints_stable(self) -> None:
        root = fb2_mod.parse_fb2(fb2_document())
        images = fb2_mod.fb2_images(root)
        chapters = fb2_mod.fb2_chapters_text(root)
        first = compute_fingerprints(root, chapters, images)
        second = compute_fingerprints(root, chapters, images)
        assert first.visible_text == second.visible_text
        assert first.structure == second.structure


class TestFB2Transform:
    def test_prose_compact_keeps_only_cover(self) -> None:
        root = fb2_mod.parse_fb2(fb2_document(body_images=3))
        serialized, actions, cover_info = fb2_mod.transform_fb2(root, PROFILE)

        new_root = fb2_mod.parse_fb2(serialized)
        binaries = list(new_root.iter(f"{{{fb2_mod.FB2_NS}}}binary"))
        assert len(binaries) == 1
        assert binaries[0].get("id") == "cover.png"
        assert cover_info["status"] == "ok"
        assert any(a.kind.value == "remove_body_images" for a in actions)

    def test_text_invariant_preserved(self) -> None:
        original = fb2_mod.parse_fb2(fb2_document(body_images=2, sections=4))
        before = visible_text(original)

        serialized, _actions, _cover = fb2_mod.transform_fb2(
            fb2_mod.parse_fb2(fb2_document(body_images=2, sections=4)),
            PROFILE,
        )
        after = visible_text(fb2_mod.parse_fb2(serialized))
        assert before == after

    def test_no_cover_marks_review(self) -> None:
        root = fb2_mod.parse_fb2(fb2_document(cover_id=None, body_images=1))
        _serialized, _actions, cover_info = fb2_mod.transform_fb2(root, PROFILE)
        assert cover_info["status"] == "review"
        assert "no coverpage" in cover_info["reason"]

    def test_ambiguous_cover_marks_review(self) -> None:
        document = fb2_document().replace(
            b"<coverpage><image l:href='#cover.png'/></coverpage>",
            b"<coverpage><image l:href='#cover.png'/><image l:href='#inner0.png'/></coverpage>",
        )
        root = fb2_mod.parse_fb2(document)
        _serialized, _actions, cover_info = fb2_mod.transform_fb2(root, PROFILE)
        assert cover_info["status"] == "review"

    def test_empty_wrappers_removed(self) -> None:
        document = fb2_document().replace(
            "<p>Текст главы 1.".encode(),
            "<p></p><p>   </p><p>Текст главы 1.".encode(),
        )
        root = fb2_mod.parse_fb2(document)
        serialized, actions, _ = fb2_mod.transform_fb2(root, PROFILE)
        kinds = [a.kind.value for a in actions]
        assert "remove_empty_wrappers" in kinds
        assert b"<p></p>" not in serialized

    def test_document_id_generated_when_missing(self) -> None:
        document = fb2_document().replace(
            b"<document-info><id>fixture-0001</id></document-info>",
            b"",
        )
        root = fb2_mod.parse_fb2(document)
        serialized, actions, _ = fb2_mod.transform_fb2(root, PROFILE)
        assert b"<id>" in serialized
        assert any(
            a.detail.get("document_id_generated")
            for a in actions
            if a.kind.value == "normalize_metadata"
        )

    def test_xxe_entity_not_resolved(self) -> None:
        evil = (
            b'<?xml version="1.0"?>'
            b'<!DOCTYPE FictionBook [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
            b'<FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0">'
            b"<body><section><p>&xxe;</p></section></body></FictionBook>"
        )
        root = fb2_mod.parse_fb2(evil)
        text = visible_text(root)
        assert "root:" not in text  # entity content never loaded


class TestEPUBTransform:
    def test_prose_compact_keeps_only_cover(self) -> None:
        book = epub_mod.parse_epub(epub_document(inner_images=3))
        serialized, actions, cover_info = epub_mod.transform_epub(book, PROFILE)

        new_book = epub_mod.parse_epub(serialized)
        image_files = [
            name for name in new_book.original if name.endswith((".png", ".jpg", ".svg"))
        ]
        assert image_files == ["OEBPS/cover.png"]
        assert cover_info["status"] == "ok"
        assert any(a.kind.value == "remove_unused_binaries" for a in actions)

    def test_text_invariant_preserved(self) -> None:
        book = epub_mod.parse_epub(epub_document(inner_images=2, chapters=4))
        before = epub_mod.epub_visible_text(book)

        book2 = epub_mod.parse_epub(epub_document(inner_images=2, chapters=4))
        serialized, _actions, _cover = epub_mod.transform_epub(book2, PROFILE)
        after = epub_mod.epub_visible_text(epub_mod.parse_epub(serialized))
        assert before == after

    def test_mimetype_first_and_stored(self) -> None:
        import io
        import zipfile

        book = epub_mod.parse_epub(epub_document())
        serialized, _actions, _cover = epub_mod.transform_epub(book, PROFILE)
        with zipfile.ZipFile(io.BytesIO(serialized)) as archive:
            infos = archive.infolist()
            assert infos[0].filename == "mimetype"
            assert infos[0].compress_type == zipfile.ZIP_STORED

    def test_no_cover_metadata_marks_review(self) -> None:
        book = epub_mod.parse_epub(epub_document(cover_meta=False))
        _serialized, _actions, cover_info = epub_mod.transform_epub(book, PROFILE)
        assert cover_info["status"] == "review"

    def test_invalid_epub_rejected(self) -> None:
        with pytest.raises(epub_mod.EPUBParseError):
            epub_mod.parse_epub(b"PK\x03\x04 garbage")

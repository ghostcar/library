"""Unit tests: EPUBCheck runner (availability, parsing, skip path)."""

from __future__ import annotations

from pathlib import Path

from portal.modules.library.infrastructure.normalizer.epubcheck import (
    EpubCheckResult,
    parse_epubcheck_xml,
    run_epubcheck,
)


class TestAvailability:
    def test_unavailable_locally_returns_skipped(self, monkeypatch) -> None:

        monkeypatch.setattr(
            "portal.modules.library.infrastructure.normalizer.epubcheck.get_settings",
            lambda: type(
                "S",
                (),
                {"epubcheck_jar": ""},
            )(),
        )
        result = run_epubcheck(Path(__file__))  # any path; tool unavailable anyway
        assert result.available is False
        assert result.valid is None  # skipped, not invalid


class TestParsing:
    def test_parse_xml_counts(self) -> None:
        xml = """<epubCheck>
          <item location="x.epub" severity="error">msg</item>
          <item severity="warning">w</item>
          <item severity="fatal">f</item>
        </epubCheck>"""
        counts = parse_epubcheck_xml(xml)
        assert counts == {"error": 1, "warning": 1, "fatal": 1}

    def test_parse_garbage_returns_zeros(self) -> None:
        assert parse_epubcheck_xml("not xml") == {"error": 0, "warning": 0, "fatal": 0}


class TestResultShape:
    def test_skipped_shape(self) -> None:
        r = EpubCheckResult(available=False)
        assert r.valid is None
        assert r.error_count == 0

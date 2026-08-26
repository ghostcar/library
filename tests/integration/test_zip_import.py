"""Integration tests for ZIP archive upload."""

from __future__ import annotations

from typing import Any

import httpx
import pytest


FB2_BYTES = b"""\
<?xml version="1.0" encoding="utf-8"?>
<FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0">
  <body><section><p>Archive test book.</p></section></body>
</FictionBook>"""


@pytest.fixture
async def authed(app: Any, client: httpx.AsyncClient) -> httpx.AsyncClient:
    resp = await client.post(
        "/auth/register",
        json={"email": "zip-test@example.com", "password": "test-password-123"},
    )
    assert resp.status_code == 201
    return client


class TestZipUpload:
    async def test_zip_with_two_fb2_imports_both(
        self, authed: httpx.AsyncClient, tmp_path: Any,
    ) -> None:
        import io, zipfile

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("Author1 -- Title1.fb2", FB2_BYTES)
            zf.writestr("Author2 -- Title2.fb2", FB2_BYTES.replace(b"Archive test", b"Second"))
        zip_bytes = buf.getvalue()

        resp = await authed.post(
            "/library/import/upload",
            files=[("files", ("archive.zip", zip_bytes, "application/zip"))],
            follow_redirects=False,
        )
        assert resp.status_code == 303

        # check batch completed
        page = await authed.get("/library/import")
        assert page.status_code == 200
        assert "archive.zip" not in page.text  # original archive not stored as item

    async def test_zip_with_no_books_rejected(
        self, authed: httpx.AsyncClient,
    ) -> None:
        import io, zipfile

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("readme.txt", b"hello world")
        zip_bytes = buf.getvalue()

        resp = await authed.post(
            "/library/import/upload",
            files=[("files", ("no-books.zip", zip_bytes, "application/zip"))],
            follow_redirects=False,
        )
        assert resp.status_code == 303

        page = await authed.get("/library/import")
        assert page.status_code == 200
        assert "no-books.zip" in page.text
        assert "нет FB2/EPUB" in page.text or "no FB2/EPUB" in page.text or "архив" in page.text.lower()

    async def test_epub_not_expanded_as_archive(
        self, authed: httpx.AsyncClient,
    ) -> None:
        import io, zipfile

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("mimetype", "application/epub+zip")
            zf.writestr("META-INF/container.xml", "<container/>")
        epub_bytes = buf.getvalue()

        resp = await authed.post(
            "/library/import/upload",
            files=[("files", ("book.epub", epub_bytes, "application/epub+zip"))],
            follow_redirects=False,
        )
        assert resp.status_code == 303

    async def test_mixed_files_and_zip(
        self, authed: httpx.AsyncClient,
    ) -> None:
        import io, zipfile

        fb2 = b'<?xml version="1.0"?><FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0"><body><section><p>X</p></section></body></FictionBook>'
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("Archived -- Book.fb2", fb2)
        zip_bytes = buf.getvalue()

        resp = await authed.post(
            "/library/import/upload",
            files=[
                ("files", ("standalone.fb2", fb2, "application/xml")),
                ("files", ("bundle.zip", zip_bytes, "application/zip")),
            ],
            follow_redirects=False,
        )
        assert resp.status_code == 303

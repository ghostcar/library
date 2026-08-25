"""Golden fixtures: synthetic FB2/EPUB builders (no copyrighted content)."""

from __future__ import annotations

import base64
import io
import zipfile

COVER_PIXEL = bytes.fromhex(
    # 1x1 PNG, generated once and frozen as fixture
    "89504e470d0a1a0a0000000d49484452000000010000000108020000009077"
    "53de0000000c4944415408d763f8cfc00000030101"
    "00cf9a5e1c0000000049454e44ae426082",
)


def fb2_document(
    *,
    title: str = "Синтетическая книга",
    sections: int = 3,
    cover_id: str | None = "cover.png",
    body_images: int = 0,
) -> bytes:
    coverpage = f"<coverpage><image l:href='#{cover_id}'/></coverpage>" if cover_id else ""
    cover_binary = (
        f"<binary id='{cover_id}' content-type='image/png'>"
        f"{base64.b64encode(COVER_PIXEL).decode()}</binary>"
        if cover_id
        else ""
    )
    body_images_xml = "".join(
        f"<p>До картинки {i}.</p><image l:href='#inner{i}.png'/><p>После картинки {i}.</p>"
        for i in range(body_images)
    )
    inner_binaries = "".join(
        f"<binary id='inner{i}.png' content-type='image/png'>"
        f"{base64.b64encode(COVER_PIXEL).decode()}</binary>"
        for i in range(body_images)
    )
    sections_xml = "".join(
        f"<section id='sec-{i + 1}'><title><p>Глава {i + 1}</p></title>"
        f"<p>Текст главы {i + 1}.  Много   пробелов.</p>"
        f"{body_images_xml if i == 0 else ''}</section>"
        for i in range(sections)
    )
    document = (
        '<?xml version="1.0" encoding="utf-8"?>'
        f'<FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0" '
        f'xmlns:l="http://www.w3.org/1999/xlink">'
        "<description>"
        "<title-info>"
        f"<book-title>{title}</book-title>"
        f"{coverpage}"
        "</title-info>"
        "<document-info><id>fixture-0001</id></document-info>"
        "</description>"
        f"<body>{sections_xml}</body>"
        f"{cover_binary}{inner_binaries}"
        "</FictionBook>"
    )
    return document.encode()


def epub_document(
    *,
    title: str = "Синтетическая EPUB книга",
    chapters: int = 3,
    cover: bool = True,
    cover_meta: bool = True,
    inner_images: int = 0,
) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        archive.writestr(
            "META-INF/container.xml",
            '<?xml version="1.0"?><container version="1.0" '
            'xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
            '<rootfiles><rootfile full-path="OEBPS/content.opf" '
            'media-type="application/oebps-package+xml"/></rootfiles></container>',
        )
        manifest_items = [
            '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
        ]
        spine_refs = ['<itemref idref="nav"/>']
        for i in range(1, chapters + 1):
            manifest_items.append(
                f'<item id="ch{i}" href="ch{i}.xhtml" media-type="application/xhtml+xml"/>',
            )
            spine_refs.append(f'<itemref idref="ch{i}"/>')

        images: list[str] = []
        if cover:
            archive.writestr("OEBPS/cover.png", COVER_PIXEL)
            images.append("cover")
            properties = ' properties="cover-image"' if cover_meta else ""
            meta = '<meta name="cover" content="cover-image"/>' if cover_meta else ""
            manifest_items.append(
                f'<item id="cover-image" href="cover.png" media-type="image/png"{properties}/>',
            )
        for i in range(inner_images):
            archive.writestr(f"OEBPS/inner{i}.png", COVER_PIXEL)
            manifest_items.append(
                f'<item id="inner{i}" href="inner{i}.png" media-type="image/png"/>',
            )
            images.append(f"inner{i}")

        archive.writestr(
            "OEBPS/content.opf",
            '<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" '
            'version="3.0" unique-identifier="uid">'
            '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
            f"<dc:title>{title}</dc:title>"
            '<dc:identifier id="uid">urn:uuid:12345678-1234-1234-1234-123456789012</dc:identifier>'
            f"{meta}"
            "</metadata>"
            f"<manifest>{''.join(manifest_items)}</manifest>"
            f"<spine>{''.join(spine_refs)}</spine></package>",
        )
        archive.writestr(
            "OEBPS/nav.xhtml",
            '<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Навигация</title></head>'
            "<body><nav><ol><li>Глава 1</li></ol></nav></body></html>",
        )
        for i in range(1, chapters + 1):
            img_tags = "".join(f'<img src="inner{j}.png" alt=""/>' for j in range(inner_images))
            archive.writestr(
                f"OEBPS/ch{i}.xhtml",
                '<html xmlns="http://www.w3.org/1999/xhtml"><head>'
                f"<title>Глава {i}</title></head><body>"
                f"<h1>Глава {i}</h1><p>Текст главы {i}.  Много   пробелов.</p>{img_tags}"
                "</body></html>",
            )
    return buffer.getvalue()

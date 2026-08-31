from portal.modules.library.infrastructure.continuation_links import extract_continuation_links


def test_extracts_only_public_links_with_continuation_context() -> None:
    content = """<?xml version="1.0" encoding="utf-8"?>
<FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0"
 xmlns:l="http://www.w3.org/1999/xlink"><body><section><p>
  Продолжение цикла: <a l:href="https://example.com/next">новая книга</a>.
  <a l:href="mailto:test@example.com">mail</a>
  <a l:href="https://example.com/other">other</a>
</p></section></body></FictionBook>""".encode()

    links = extract_continuation_links(content)

    assert [(link.url, link.context) for link in links] == [
        ("https://example.com/next", "Продолжение цикла: новая книга . mail other")
    ]


def test_ignores_links_without_continuation_signal() -> None:
    content = """<FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0"
 xmlns:l="http://www.w3.org/1999/xlink"><body><section><p>
  <a l:href="https://example.com/author">Автор</a>
</p></section></body></FictionBook>""".encode()

    assert extract_continuation_links(content) == []

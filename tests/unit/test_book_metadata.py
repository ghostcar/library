from portal.modules.library.application.book_metadata import extract_fb2_metadata


def test_extracts_ordered_fb2_title_info_metadata() -> None:
    content = """<FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0">
    <description><title-info><book-title>Название</book-title>
    <author><first-name>Иван</first-name><last-name>Первый</last-name></author>
    <author><nickname>Псевдоним</nickname></author>
    <sequence name="Цикл" number="02"/><lang>ru</lang>
    </title-info></description></FictionBook>""".encode()
    metadata = extract_fb2_metadata(content)
    assert metadata.title == "Название"
    assert metadata.authors == ("Иван Первый", "Псевдоним")
    assert metadata.series == "Цикл"
    assert metadata.series_index_raw == "02"
    assert metadata.language == "ru"


def test_extracts_namespace_less_fb2_metadata() -> None:
    content = (
        "<FictionBook><description><title-info><book-title>Книга</book-title>"
        "<author><last-name>Автор</last-name></author>"
        "</title-info></description></FictionBook>"
    ).encode()
    metadata = extract_fb2_metadata(content)
    assert metadata.title == "Книга"
    assert metadata.authors == ("Автор",)

from pathlib import Path

from portal.web.middleware import _HEADERS

ROOT = Path(__file__).resolve().parents[1]


def test_templates_do_not_use_inline_styles() -> None:
    templates = list((ROOT / "src" / "portal").rglob("*.html"))
    offenders = [str(path.relative_to(ROOT)) for path in templates if "style=" in path.read_text()]
    assert offenders == []


def test_csp_forbids_inline_scripts_and_styles() -> None:
    csp = _HEADERS["Content-Security-Policy"]
    assert "unsafe-inline" not in csp
    assert "style-src 'self'" in csp
    assert "script-src 'self'" in csp

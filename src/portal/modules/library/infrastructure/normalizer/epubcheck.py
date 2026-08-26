"""EPUBCheck runner (master prompt 7.6): validates EPUB derivatives.

Availability depends on Java + jar (present in the Docker image,
optional locally). Unavailable -> validation recorded as skipped.
"""

from __future__ import annotations

import shutil
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from portal.core.config.config import get_settings

_FATAL = "FATAL"


@dataclass(slots=True)
class EpubCheckResult:
    available: bool
    valid: bool | None = None  # None = skipped (tool unavailable)
    error_count: int = 0
    warning_count: int = 0
    messages: list[str] = field(default_factory=list)


def is_available() -> bool:
    jar = get_settings().epubcheck_jar
    if not jar or not Path(jar).is_file():
        return False
    java = shutil.which("java")
    if java is None:
        return False
    try:
        subprocess.run(  # noqa: S603 - fixed system binary
            [java, "-version"],
            capture_output=True,
            timeout=15,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return True


def run_epubcheck(epub_path: Path) -> EpubCheckResult:
    """Run EPUBCheck on a file. Raises nothing; failures -> available+invalid."""
    jar = get_settings().epubcheck_jar
    if not is_available():
        return EpubCheckResult(available=False)

    java = shutil.which("java")
    if java is None:
        return EpubCheckResult(available=False)
    try:
        proc = subprocess.run(  # noqa: S603 - fixed jar from config, no shell
            [java, "-jar", jar, "--quiet", str(epub_path)],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return EpubCheckResult(
            available=True,
            valid=False,
            messages=[f"epubcheck invocation failed: {exc}"],
        )

    output = (proc.stderr or "") + (proc.stdout or "")
    messages = [line for line in output.splitlines() if line.strip()]
    error_count = sum(_FATAL in line or "ERROR(" in line for line in messages)
    warning_count = sum("WARNING(" in line for line in messages)

    if proc.returncode not in {0, 1}:  # 0=valid, 1=warnings/typos handled below
        return EpubCheckResult(
            available=True,
            valid=False,
            error_count=error_count or 1,
            warning_count=warning_count,
            messages=messages[:50] or [f"epubcheck exit {proc.returncode}"],
        )

    return EpubCheckResult(
        available=True,
        valid=(proc.returncode == 0),
        error_count=error_count,
        warning_count=warning_count,
        messages=messages[:50],
    )


def parse_epubcheck_xml(xml_output: str) -> dict[str, int]:
    """Count items by severity attribute (EPUBCheck XML output shape)."""
    counts = {"error": 0, "warning": 0, "fatal": 0}
    try:
        root = ET.fromstring(xml_output)  # noqa: S314
    except ET.ParseError:
        return counts
    for item in root.iter():
        severity = (item.get("severity") or item.tag.rsplit("}", 1)[-1]).lower()
        if severity in counts:
            counts[severity] += 1
    return counts

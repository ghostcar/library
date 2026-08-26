"""Domain value objects."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class Sha256:
    """Content hash addressing for assets (master prompt 5.2)."""

    value: str

    def __post_init__(self) -> None:
        if not _SHA256_RE.match(self.value):
            msg = f"invalid sha256 hex digest: {self.value!r}"
            raise ValueError(msg)

    def __str__(self) -> str:
        return self.value

    @property
    def prefix(self) -> str:
        """Two-level storage prefix (ab/cdef...)."""
        return self.value[:2]


@dataclass(frozen=True, slots=True)
class SeriesIndex:
    """Book number within a series.

    Raw string is preserved as-is; a normalized sort key is derived
    when unambiguous. Supports "0", "0.5", "1.1", ranges "2-3",
    and unknown order (master prompt 5.2).
    """

    raw: str
    sort_key: Decimal | None

    def __post_init__(self) -> None:
        if not self.raw or not self.raw.strip():
            msg = "series index raw value must not be empty"
            raise ValueError(msg)

    @classmethod
    def parse(cls, raw: str) -> SeriesIndex:
        text = raw.strip()
        head = text.split("-", 1)[0].strip() if "-" in text else text
        sort_key: Decimal | None = None
        try:
            value = Decimal(head.replace(",", "."))
            if value.is_finite():
                sort_key = value
        except InvalidOperation:
            sort_key = None
        return cls(raw=text, sort_key=sort_key)

    def __str__(self) -> str:
        return self.raw

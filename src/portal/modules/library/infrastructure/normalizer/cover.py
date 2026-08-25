"""Cover image optimization (master prompt 7.4).

Only JPEG/PNG are re-encoded; anything else passes through unchanged
(no risky format conversion). Resize keeps aspect ratio, never upscales.
"""

from __future__ import annotations

import io
from typing import Any

from PIL import Image

_OPTIMIZABLE = {"image/jpeg": "JPEG", "image/png": "PNG"}
_JPEG_QUALITY = 85


def optimize_cover(content: bytes, max_dimension: int) -> tuple[bytes, dict[str, Any]]:
    """Return (optimized bytes, meta). Falls back to original on any error."""
    meta: dict[str, Any] = {"optimized": False, "reason": None}
    try:
        with Image.open(io.BytesIO(content)) as image:
            fmt = (image.format or "").upper()
            if fmt not in {"JPEG", "PNG"}:
                meta["reason"] = f"format {fmt} is not re-encoded"
                return content, meta

            width, height = image.size
            if max(width, height) <= max_dimension:
                meta["reason"] = "already within limit"
                return content, meta

            scale = max_dimension / max(width, height)
            new_size = (max(1, round(width * scale)), max(1, round(height * scale)))
            resized = image.resize(new_size, Image.Resampling.LANCZOS)

            buffer = io.BytesIO()
            if fmt == "JPEG":
                resized.convert("RGB").save(
                    buffer,
                    format="JPEG",
                    quality=_JPEG_QUALITY,
                    optimize=True,
                )
            else:
                resized.save(buffer, format="PNG", optimize=True)
            optimized = buffer.getvalue()

            meta.update(
                {
                    "optimized": True,
                    "original_size_px": [width, height],
                    "new_size_px": list(new_size),
                    "content_type": f"image/{fmt.lower()}",
                    "new_size": len(optimized),
                },
            )
            return optimized, meta
    except (OSError, ValueError) as exc:
        meta["reason"] = f"optimization skipped: {exc}"
        return content, meta

"""Import all ORM models so Base.metadata is complete.

Used by migrations/env.py, the worker and any tooling that needs the full
schema (FK resolution requires every referenced table to be registered).
"""

from __future__ import annotations

# fmt: off
from portal.core.auth import orm as _auth_orm  # noqa: F401
from portal.core.database.engine import Base
from portal.core.events import orm as _events_orm  # noqa: F401
from portal.core.jobs import orm as _jobs_orm  # noqa: F401
from portal.modules.library.ai import orm as _ai_orm  # noqa: F401
from portal.modules.library.infrastructure import import_orm as _import_orm  # noqa: F401
from portal.modules.library.infrastructure import normalization_orm as _norm_orm  # noqa: F401
from portal.modules.library.infrastructure import orm as _library_orm  # noqa: F401

# fmt: on

metadata = Base.metadata


def ensure_models_imported() -> None:
    """Explicit no-op for callers that want to guarantee registration."""
    return None

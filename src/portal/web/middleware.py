"""Security headers middleware (master prompt 18.7, hardening)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from portal.core.audit.service import AuditService
from portal.core.auth.repository import AuditRepository

_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    # SSR + HTMX assets are local; inline scripts and styles are forbidden.
    "Content-Security-Policy": (
        "default-src 'self'; "
        "object-src 'none'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "img-src 'self' data:; "
        "style-src 'self'; "
        "script-src 'self'"
    ),
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        if (
            request.method in {"POST", "PUT", "PATCH", "DELETE"}
            and request.url.path.startswith("/library")
            and response.status_code < 400
            and (user_id := getattr(request.state, "auth_user_id", None)) is not None
        ):
            factory = request.app.state.container["session_factory"]
            async with factory() as session, session.begin():
                await AuditService(AuditRepository(session)).log(
                    "portal_action",
                    user_id=user_id,
                    actor_ip=request.client.host if request.client else None,
                    entity_type="http_route",
                    entity_id=request.url.path,
                    details={"method": request.method, "status_code": response.status_code},
                )
        for name, value in _HEADERS.items():
            response.headers.setdefault(name, value)
        return response

"""Unit tests: JWT service, passwords, token hashing."""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import jwt as pyjwt
import pytest

from portal.core.auth.domain import SCOPE_PORTAL_FULL, AuthTokenType
from portal.core.auth.jwt_service import TokenService, generate_raw_token, hash_token
from portal.core.auth.passwords import hash_password, verify_password
from portal.core.config.config import AppEnv, Settings


def make_settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "app_env": AppEnv.TEST,
        "jwt_secret": "unit-test-secret",
        "_env_file": None,
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


class TestPasswords:
    def test_roundtrip(self) -> None:
        hashed = hash_password("correct horse battery staple")
        assert verify_password(hashed, "correct horse battery staple")
        assert not verify_password(hashed, "wrong password")

    def test_hash_is_argon2id(self) -> None:
        assert hash_password("x" * 20).startswith("$argon2id$")

    def test_malformed_hash_is_false_not_crash(self) -> None:
        assert not verify_password("not-a-hash", "whatever")


class TestTokenService:
    def test_issue_and_verify_roundtrip(self) -> None:
        service = TokenService(make_settings())
        user_id = str(uuid4())
        token, expires_at = service.issue_access_token(user_id, [SCOPE_PORTAL_FULL])
        principal = service.verify(token)
        assert principal.user_id == user_id
        assert principal.has_scope(SCOPE_PORTAL_FULL)
        assert principal.token_type is AuthTokenType.API
        assert principal.expires_at <= expires_at + timedelta(seconds=1)

    def test_expired_token_rejected(self) -> None:
        service = TokenService(make_settings(access_token_ttl_minutes=-1))
        token, _ = service.issue_access_token(str(uuid4()), [SCOPE_PORTAL_FULL])
        with pytest.raises(pyjwt.ExpiredSignatureError):
            service.verify(token)

    def test_wrong_secret_rejected(self) -> None:
        token, _ = TokenService(make_settings()).issue_access_token(str(uuid4()), [])
        other = TokenService(  # noqa: S106
            make_settings(jwt_secret="another-secret-0123456789abcdef0123456789ab"),
        )
        with pytest.raises(pyjwt.InvalidTokenError):
            other.verify(token)

    def test_garbage_rejected(self) -> None:
        service = TokenService(make_settings())
        with pytest.raises(pyjwt.InvalidTokenError):
            service.verify("garbage.token.value")

    def test_scope_check_negative(self) -> None:
        service = TokenService(make_settings())
        token, _ = service.issue_access_token(str(uuid4()), ["library:opds:read"])
        principal = service.verify(token)
        assert principal.has_scope("library:opds:read")
        assert not principal.has_scope("portal:admin")


class TestTokenHashing:
    def test_hash_token_is_sha256_hex(self) -> None:
        digest = hash_token("some-raw-token")
        assert len(digest) == 64
        int(digest, 16)  # must be hex

    def test_generate_raw_token_prefixed_and_unique(self) -> None:
        a, b = generate_raw_token("prt"), generate_raw_token("prt")
        assert a.startswith("prt_")
        assert b.startswith("prt_")
        assert a != b

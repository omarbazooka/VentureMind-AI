import logging
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Header, HTTPException, status
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)

# Cached JWKS client instance.
_jwk_client: jwt.PyJWKClient | None = None


def _expected_issuer() -> str | None:
    if not settings.supabase_url:
        return None
    return f"{settings.supabase_url.rstrip('/')}/auth/v1"


def get_jwk_client() -> jwt.PyJWKClient | None:
    global _jwk_client
    issuer = _expected_issuer()
    if _jwk_client is None and issuer:
        _jwk_client = jwt.PyJWKClient(
            f"{issuer}/.well-known/jwks.json",
            cache_keys=True,
        )
    return _jwk_client


class AuthenticatedUser(BaseModel):
    user_id: UUID
    email: str | None = None
    role: str = "authenticated"


def enforce_idea_ownership(
    *,
    owner_user_id: UUID | None,
    user: AuthenticatedUser | None,
) -> None:
    """Reject access to an owned idea unless the authenticated user owns it.

    Unowned rows remain accessible for legacy/demo compatibility. New authenticated
    app flows should create owned ideas and therefore receive the stricter boundary.
    """
    if owner_user_id is not None and (
        user is None or user.user_id != owner_user_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: you do not have permission to access this idea",
        )


def _decode_verified_token(
    *,
    token: str,
    key: object,
    algorithms: list[str],
) -> dict:
    issuer = _expected_issuer()
    if issuer is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase URL is not configured",
        )

    return jwt.decode(
        token,
        key,
        algorithms=algorithms,
        audience=settings.supabase_jwt_audience,
        issuer=issuer,
        options={
            "require": ["exp", "iss", "sub", "aud"],
        },
    )


def _verify_token(token: str) -> dict:
    """Verify a Supabase user access token and its core identity claims."""
    try:
        header = jwt.get_unverified_header(token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    alg = header.get("alg", "HS256")

    # Modern Supabase signing-key projects expose asymmetric keys through JWKS.
    if alg in ("RS256", "ES256"):
        jwk_client = get_jwk_client()
        if jwk_client is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Supabase URL not configured for JWT verification",
            )
        try:
            signing_key = jwk_client.get_signing_key_from_jwt(token)
            return _decode_verified_token(
                token=token,
                key=signing_key.key,
                algorithms=[alg],
            )
        except jwt.PyJWTError as exc:
            logger.warning("Supabase asymmetric JWT verification failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

    # Legacy HS256 fallback. Prefer asymmetric Supabase signing keys for new projects.
    if alg == "HS256":
        secret = (
            settings.supabase_jwt_secret.get_secret_value()
            if settings.supabase_jwt_secret
            else None
        )
        if not secret:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="HS256 verification not configured on server",
                headers={"WWW-Authenticate": "Bearer"},
            )
        try:
            return _decode_verified_token(
                token=token,
                key=secret,
                algorithms=["HS256"],
            )
        except jwt.PyJWTError as exc:
            logger.warning("Supabase HS256 JWT verification failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unsupported authentication token algorithm",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    x_dev_user_id: Annotated[str | None, Header()] = None,
) -> AuthenticatedUser:
    """Extract and strictly verify the authenticated user from Supabase JWT.

    Identity always comes from the verified token subject. A development bypass is
    available only when it is explicitly enabled and the app environment is dev/test.
    """
    if (
        settings.enable_dev_auth_bypass
        and settings.app_env in ("test", "development")
        and x_dev_user_id
    ):
        try:
            dev_uuid = UUID(x_dev_user_id)
            logger.info("Using dev auth bypass user %s", dev_uuid)
            return AuthenticatedUser(
                user_id=dev_uuid,
                email="dev@venturemind.ai",
                role="authenticated",
            )
        except ValueError:
            pass

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header scheme. Expected 'Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = _verify_token(token)
    sub = payload.get("sub")

    try:
        user_id = UUID(sub)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user identity in authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    return AuthenticatedUser(
        user_id=user_id,
        email=payload.get("email"),
        role=payload.get("role", "authenticated"),
    )


def get_optional_user(
    authorization: Annotated[str | None, Header()] = None,
    x_dev_user_id: Annotated[str | None, Header()] = None,
) -> AuthenticatedUser | None:
    """Return an authenticated user when auth material is present, else None."""
    if authorization or (
        settings.enable_dev_auth_bypass
        and settings.app_env in ("test", "development")
        and x_dev_user_id
    ):
        return get_current_user(
            authorization=authorization,
            x_dev_user_id=x_dev_user_id,
        )
    return None

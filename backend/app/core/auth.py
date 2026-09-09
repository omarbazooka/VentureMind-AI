import logging
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, Header, HTTPException, status
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)

# Cached JWKS client instance
_jwk_client: jwt.PyJWKClient | None = None


def get_jwk_client() -> jwt.PyJWKClient | None:
    global _jwk_client
    if _jwk_client is None and settings.supabase_url:
        jwks_url = f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
        _jwk_client = jwt.PyJWKClient(jwks_url, cache_keys=True)
    return _jwk_client


class AuthenticatedUser(BaseModel):
    user_id: UUID
    email: str | None = None
    role: str = "authenticated"


def _verify_token(token: str) -> dict:
    """Verify Supabase JWT token via JWKS (asymmetric) or shared secret (symmetric)."""
    try:
        header = jwt.get_unverified_header(token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    alg = header.get("alg", "HS256")

    # 1. Asymmetric verification (ES256, RS256 - default modern Supabase configuration)
    if alg in ("RS256", "ES256"):
        jwk_client = get_jwk_client()
        if jwk_client is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Supabase URL not configured for asymmetric JWT verification",
            )
        try:
            signing_key = jwk_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=[alg],
                audience=settings.supabase_jwt_audience,
            )
            return payload
        except jwt.PyJWTError as exc:
            logger.warning("Supabase asymmetric JWT verification failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid authentication token: {exc}",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

    # 2. Symmetric verification (HS256 - legacy Supabase secret)
    elif alg == "HS256":
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
            payload = jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                audience=settings.supabase_jwt_audience,
            )
            return payload
        except jwt.PyJWTError as exc:
            logger.warning("Supabase HS256 JWT verification failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid authentication token: {exc}",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Unsupported token algorithm: {alg}",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    x_dev_user_id: Annotated[str | None, Header()] = None,
) -> AuthenticatedUser:
    """Extract and strictly verify the authenticated user from Supabase JWT.

    Never trusts request-provided user_id in payload.
    Any dev auth bypass is restricted to test/dev environment with explicit opt-in.
    """
    # Guarded Test / Dev Auth Bypass (strictly disabled by default)
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
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject (sub) claim",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = UUID(sub)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID format in token subject",
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
    """Return authenticated user if Authorization header is provided, else None."""
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

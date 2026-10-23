from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings

ISSUER = f"{settings.supabase_url}/auth/v1"
_jwks = jwt.PyJWKClient(f"{ISSUER}/.well-known/jwks.json", cache_keys=True, lifespan=600)
_bearer = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    id: str
    email: str | None


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> CurrentUser:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in")
    try:
        key = _jwks.get_signing_key_from_jwt(creds.credentials)
        claims = jwt.decode(
            creds.credentials,
            key.key,
            algorithms=["ES256", "RS256"],
            audience="authenticated",
            issuer=ISSUER,
        )
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    return CurrentUser(id=claims["sub"], email=claims.get("email"))
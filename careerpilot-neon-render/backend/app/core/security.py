import secrets
from threading import BoundedSemaphore
from datetime import datetime, timedelta, timezone
from uuid import UUID
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.db.session import get_db
from app.models.user import AuthSession, User

bearer = HTTPBearer(auto_error=False)
password_hasher = PasswordHasher(memory_cost=19456, time_cost=2, parallelism=1)
# Bound Argon2 memory consumption on small free-tier instances.
_hash_slots = BoundedSemaphore(2)
# Same Argon2 work for missing users reduces timing-based account discovery.
DUMMY_HASH = password_hasher.hash(secrets.token_urlsafe(24))


def hash_password(password: str) -> str:
    with _hash_slots:
        return password_hasher.hash(password)


def verify_password(hashed: str, password: str) -> bool:
    try:
        with _hash_slots:
            return password_hasher.verify(hashed, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def signing_secret() -> str:
    secret = get_settings().jwt_secret_key
    if len(secret.encode('utf-8')) < 32:
        raise HTTPException(status_code=503, detail='Authentication is not configured securely.')
    return secret


def create_access_token(user_id: UUID, session_id: UUID, expires_at: datetime) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    return jwt.encode({'sub': str(user_id), 'jti': str(session_id), 'iat': now, 'exp': expires_at,
                       'iss': settings.jwt_issuer, 'aud': settings.jwt_audience}, signing_secret(), algorithm='HS256')


def unauthorized() -> HTTPException:
    return HTTPException(status_code=401, detail='Invalid or expired access token.', headers={'WWW-Authenticate': 'Bearer'})


def require_bearer(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> str:
    if not credentials or credentials.scheme.lower() != 'bearer':
        raise HTTPException(status_code=401, detail='Authentication required.', headers={'WWW-Authenticate': 'Bearer'})
    return credentials.credentials


def authenticated_session(token: str = Depends(require_bearer), db: Session = Depends(get_db)) -> tuple[User, AuthSession]:
    settings = get_settings()
    try:
        payload = jwt.decode(token, signing_secret(), algorithms=['HS256'],
                             issuer=settings.jwt_issuer, audience=settings.jwt_audience,
                             options={'require': ['sub', 'jti', 'iat', 'exp', 'iss', 'aud']})
        user_id, session_id = UUID(payload['sub']), UUID(payload['jti'])
    except (jwt.PyJWTError, ValueError, TypeError, KeyError) as exc:
        raise unauthorized() from exc
    now = datetime.now(timezone.utc)
    auth_session = db.scalar(select(AuthSession).where(AuthSession.id == session_id, AuthSession.user_id == user_id,
                                                        AuthSession.revoked_at.is_(None), AuthSession.expires_at > now))
    user = db.get(User, user_id) if auth_session else None
    if not auth_session or not user:
        raise unauthorized()
    return user, auth_session


def current_user(auth: tuple[User, AuthSession] = Depends(authenticated_session)) -> UUID:
    return auth[0].id

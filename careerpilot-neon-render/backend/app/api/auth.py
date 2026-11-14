from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.rate_limit import limit_auth_attempts
from app.core.security import DUMMY_HASH, authenticated_session, create_access_token, hash_password, signing_secret, verify_password
from app.db.session import get_db
from app.models.user import AuthSession, User
from app.schemas.auth import LoginRequest, SignupRequest, TokenResponse, UserRead

router = APIRouter(prefix='/auth', tags=['authentication'])


def issue_session(user: User, db: Session) -> TokenResponse:
    settings = get_settings()
    signing_secret()  # Fail before writing a session if signing is not configured.
    minutes = settings.access_token_minutes
    if not 1 <= minutes <= 1440:
        raise HTTPException(status_code=503, detail='Authentication is not configured securely.')
    now = datetime.now(timezone.utc)
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id, AuthSession.expires_at <= now))
    auth_session = AuthSession(user_id=user.id, expires_at=now + timedelta(minutes=minutes))
    db.add(auth_session)
    db.flush()
    token = create_access_token(user.id, auth_session.id, auth_session.expires_at)
    db.commit()
    return TokenResponse(access_token=token, expires_in=minutes * 60, user=UserRead.model_validate(user))


@router.post('/signup', response_model=TokenResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(limit_auth_attempts)])
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    signing_secret()
    email = str(payload.email).strip().lower()
    user = User(email=email, full_name=payload.full_name, password_hash=hash_password(payload.password))
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail='An account with this email already exists.') from exc
    return issue_session(user, db)


@router.post('/login', response_model=TokenResponse, dependencies=[Depends(limit_auth_attempts)])
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == str(payload.email).strip().lower()))
    valid = verify_password(user.password_hash if user else DUMMY_HASH, payload.password)
    if not valid or not user:
        raise HTTPException(status_code=401, detail='Invalid email or password.')
    return issue_session(user, db)


@router.get('/me', response_model=UserRead)
def me(auth: tuple[User, AuthSession] = Depends(authenticated_session)):
    return auth[0]


@router.post('/logout', status_code=status.HTTP_204_NO_CONTENT)
def logout(auth: tuple[User, AuthSession] = Depends(authenticated_session), db: Session = Depends(get_db)):
    auth[1].revoked_at = datetime.now(timezone.utc)
    db.commit()
    return Response(status_code=204)

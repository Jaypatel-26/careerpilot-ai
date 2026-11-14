from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.security import authenticated_session
from app.db.session import get_db
from app.models.user import AuthSession, User
from app.schemas.profile import ProfileRead, ProfileUpdate

router = APIRouter(prefix='/profile', tags=['profile'])


@router.get('', response_model=ProfileRead)
def get_profile(auth: tuple[User, AuthSession] = Depends(authenticated_session)):
    return auth[0]


@router.patch('', response_model=ProfileRead)
def update_profile(payload: ProfileUpdate, auth: tuple[User, AuthSession] = Depends(authenticated_session), db: Session = Depends(get_db)):
    user = auth[0]
    for field, value in payload.model_dump().items():
        setattr(user, field, value.strip())
    db.commit()
    db.refresh(user)
    return user

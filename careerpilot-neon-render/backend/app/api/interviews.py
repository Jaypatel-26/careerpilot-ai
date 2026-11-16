from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.security import current_user
from app.db.session import get_db
from app.models import InterviewSession
from app.schemas.interview import InterviewCreate, InterviewRead

router = APIRouter(prefix="/interviews", tags=["interviews"])


def owned_session(session_id: UUID, user_id: UUID, db: Session) -> InterviewSession:
    result = db.scalar(select(InterviewSession).where(InterviewSession.id == session_id, InterviewSession.user_id == user_id))
    if result is None:
        # Do not reveal whether another user's session exists.
        raise HTTPException(status_code=404, detail="Interview not found.")
    return result


@router.post("", response_model=InterviewRead, status_code=status.HTTP_201_CREATED)
def create_interview(payload: InterviewCreate, user_id: UUID = Depends(current_user), db: Session = Depends(get_db)):
    interview = InterviewSession(user_id=user_id, **payload.model_dump(), status="draft")
    db.add(interview)
    db.commit()
    db.refresh(interview)
    return interview


@router.get("", response_model=list[InterviewRead])
def list_interviews(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), user_id: UUID = Depends(current_user), db: Session = Depends(get_db)):
    return list(db.scalars(select(InterviewSession).where(InterviewSession.user_id == user_id).order_by(InterviewSession.created_at.desc(), InterviewSession.id.desc()).offset(offset).limit(limit)))


@router.get("/{session_id}", response_model=InterviewRead)
def get_interview(session_id: UUID, user_id: UUID = Depends(current_user), db: Session = Depends(get_db)):
    return owned_session(session_id, user_id, db)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_interview(session_id: UUID, user_id: UUID = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(owned_session(session_id, user_id, db))
    db.commit()

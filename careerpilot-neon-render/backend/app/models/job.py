import uuid
from datetime import datetime, timezone
from sqlalchemy import JSON, DateTime, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base

def utcnow(): return datetime.now(timezone.utc)

class SavedJob(Base):
    __tablename__='saved_jobs'
    __table_args__=(UniqueConstraint('user_id','job_key',name='uq_saved_job_user_key'),)
    id:Mapped[uuid.UUID]=mapped_column(Uuid,primary_key=True,default=uuid.uuid4)
    user_id:Mapped[uuid.UUID]=mapped_column(Uuid,ForeignKey('users.id',ondelete='CASCADE'),index=True,nullable=False)
    job_key:Mapped[str]=mapped_column(String(120),nullable=False)
    job:Mapped[dict]=mapped_column(JSON,nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=utcnow)

class JobMatchReport(Base):
    __tablename__='job_match_reports'
    __table_args__=(UniqueConstraint('user_id','request_id',name='uq_job_match_user_request'),)
    id:Mapped[uuid.UUID]=mapped_column(Uuid,primary_key=True,default=uuid.uuid4)
    user_id:Mapped[uuid.UUID]=mapped_column(Uuid,ForeignKey('users.id',ondelete='CASCADE'),index=True,nullable=False)
    resume_report_id:Mapped[uuid.UUID|None]=mapped_column(Uuid,ForeignKey('resume_reports.id',ondelete='SET NULL'),nullable=True)
    request_id:Mapped[uuid.UUID]=mapped_column(Uuid,nullable=False)
    input_hash:Mapped[str]=mapped_column(String(64),nullable=False)
    job_key:Mapped[str]=mapped_column(String(120),nullable=False)
    job:Mapped[dict]=mapped_column(JSON,nullable=False)
    report:Mapped[dict]=mapped_column(JSON,nullable=False)
    model_name:Mapped[str]=mapped_column(String(100),nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=utcnow)

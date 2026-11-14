from datetime import datetime
from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base

class JobSourceCache(Base):
    """Short-lived public provider snapshots; never contains resumes or secrets."""
    __tablename__='job_source_cache'
    job_key:Mapped[str]=mapped_column(String(120),primary_key=True)
    job:Mapped[dict]=mapped_column(JSON,nullable=False)
    expires_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,index=True)

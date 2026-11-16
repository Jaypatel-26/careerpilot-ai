import uuid
from datetime import datetime, timezone
from sqlalchemy import JSON, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base

def now(): return datetime.now(timezone.utc)

class CareerPlan(Base):
    __tablename__='career_plans'
    id:Mapped[uuid.UUID]=mapped_column(Uuid,primary_key=True,default=uuid.uuid4)
    user_id:Mapped[uuid.UUID]=mapped_column(Uuid,ForeignKey('users.id',ondelete='CASCADE'),nullable=False,unique=True,index=True)
    goal:Mapped[dict]=mapped_column(JSON,nullable=False)
    roadmap:Mapped[dict|None]=mapped_column(JSON,nullable=True)
    request_id:Mapped[uuid.UUID|None]=mapped_column(Uuid,nullable=True)
    input_hash:Mapped[str|None]=mapped_column(String(64),nullable=True)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=now,onupdate=now)

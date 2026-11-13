from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator


class InterviewCreate(BaseModel):
    target_role: str = Field(min_length=1, max_length=150)
    interview_type: Literal["technical", "behavioral", "mixed"]
    difficulty: Literal["beginner", "intermediate", "advanced"]
    question_count: int = Field(ge=1, le=20)

    @field_validator("target_role")
    @classmethod
    def role_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Target role cannot be blank")
        return value


class InterviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    target_role: str
    interview_type: str
    difficulty: str
    question_count: int
    status: str
    created_at: datetime
    updated_at: datetime

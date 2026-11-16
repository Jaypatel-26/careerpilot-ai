from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator


class InterviewCreate(BaseModel):
    mode: Literal["text", "voice"] = "text"
    target_role: str = Field(min_length=1, max_length=150)
    interview_type: Literal["technical", "behavioral", "mixed"]
    difficulty: Literal["beginner", "intermediate", "advanced"]
    question_count: int = Field(ge=1, le=20)
    question_focus: Literal["technical", "hr", "behavioral", "situational", "mixed"] | None = None
    experience_level: Literal["Student", "Fresher", "Experienced"] | None = None
    skills: str = Field(default="", max_length=500)

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
    mode: str = "text"
    question_focus: str | None = None
    experience_level: str | None = None
    skills: str | None = None
    created_at: datetime
    updated_at: datetime

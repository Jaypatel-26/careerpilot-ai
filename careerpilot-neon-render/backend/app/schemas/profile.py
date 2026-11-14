from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class ProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: EmailStr
    full_name: str
    target_role: str = ''
    experience_level: str = ''
    skills: str = ''
    career_goals: str = ''

    @field_validator('target_role', 'experience_level', 'skills', 'career_goals', mode='before')
    @classmethod
    def empty_if_none(cls, value):
        return value or ''


class ProfileUpdate(BaseModel):
    # The owner is derived only from the access token, never from this request.
    model_config = ConfigDict(extra='forbid')
    full_name: str = Field(min_length=1, max_length=120)
    target_role: str = Field(max_length=150)
    experience_level: Literal['', 'Student', 'Fresher', 'Experienced']
    skills: str = Field(max_length=2000)
    career_goals: str = Field(max_length=5000)

    @field_validator('full_name')
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError('Full name cannot be blank')
        return value

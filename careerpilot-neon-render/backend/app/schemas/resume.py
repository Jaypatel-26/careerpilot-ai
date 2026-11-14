from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator

class ResumeRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: UUID
    resume_text: str = Field(min_length=50,max_length=20000)
    job_description: str = Field(default='',max_length=12000)

    @field_validator('resume_text')
    @classmethod
    def check_resume(cls, value):
        value = value.strip()
        if len(value)<50:
            raise ValueError('Resume text must be at least 50 characters')
        return value

class BulletSuggestion(BaseModel):
    before: str = Field(min_length=1, max_length=1000)
    after: str = Field(min_length=1, max_length=1500)
    note: str = Field(min_length=1, max_length=1000)

class MatchAnalysis(BaseModel):
    score: int = Field(ge=0,le=100)
    matching_skills: list[str] = Field(max_length=8)
    missing_skills: list[str] = Field(max_length=8)
    matching_keywords: list[str] = Field(max_length=8)
    missing_keywords: list[str] = Field(max_length=8)
    requirements_not_covered: list[str] = Field(max_length=8)
    targeted_suggestions: list[str] = Field(max_length=8)
    project_suggestions: list[str] = Field(max_length=8)

    @field_validator('matching_skills','missing_skills','matching_keywords','missing_keywords','requirements_not_covered','targeted_suggestions','project_suggestions')
    @classmethod
    def valid_items(cls,v):
        if any(not x.strip() or len(x)>1000 for x in v): raise ValueError('Invalid item')
        return v

class ResumeAnalysis(BaseModel):
    overall_score: int = Field(ge=0,le=100)
    ats_score: int = Field(ge=0,le=100)
    strengths: list[str] = Field(max_length=8)
    weaknesses: list[str] = Field(max_length=8)
    missing_skills: list[str] = Field(max_length=8)
    missing_sections: list[str] = Field(max_length=8)
    grammar_suggestions: list[str] = Field(max_length=8)
    project_improvements: list[str] = Field(max_length=8)
    experience_suggestions: list[str] = Field(max_length=8)
    education_skills_review: list[str] = Field(max_length=8)
    formatting_suggestions: list[str] = Field(max_length=8)
    action_verbs: list[str] = Field(max_length=8)
    measurable_achievement_suggestions: list[str] = Field(max_length=8)
    bullet_improvements: list[BulletSuggestion] = Field(max_length=5)

    @field_validator('strengths','weaknesses','missing_skills','missing_sections','grammar_suggestions','project_improvements','experience_suggestions','education_skills_review','formatting_suggestions','action_verbs','measurable_achievement_suggestions')
    @classmethod
    def valid_items(cls,v):
        if any(not x.strip() or len(x)>1000 for x in v): raise ValueError('Invalid item')
        return v

class ResumeWithJob(ResumeAnalysis):
    job_match: MatchAnalysis

class ResumeRead(BaseModel):
    id: UUID
    created_at: datetime
    report: dict

from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator

class SaveJobRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    job_key:str=Field(min_length=3,max_length=120)

class JobMatchRequest(SaveJobRequest):
    request_id:UUID
    resume_report_id:UUID
    verified_resume_text:str=Field(default='',max_length=20000)

class JobMatchAnalysis(BaseModel):
    match_score:int=Field(ge=0,le=100)
    matching_skills:list[str]=Field(max_length=8)
    missing_skills:list[str]=Field(max_length=8)
    important_requirements:list[str]=Field(max_length=8)
    requirements_not_evidenced:list[str]=Field(max_length=8)
    improvements:list[str]=Field(max_length=8)
    recommended_roles:list[str]=Field(max_length=8)
    evidence_limitations:list[str]=Field(max_length=8)
    @field_validator('matching_skills','missing_skills','important_requirements','requirements_not_evidenced','improvements','recommended_roles','evidence_limitations')
    @classmethod
    def validate_items(cls,v):
        if any(not x.strip() or len(x)>1000 for x in v):raise ValueError('Invalid item')
        return v

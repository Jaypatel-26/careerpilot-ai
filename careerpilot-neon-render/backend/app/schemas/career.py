from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator

class Goal(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    role:str=Field(min_length=2,max_length=120)
    skill_level:Literal['beginner','intermediate','advanced']
    experience:Literal['student','fresher','experienced']
    daily_hours:float=Field(ge=0.5,le=8,allow_inf_nan=False)
    weeks:int=Field(ge=1,le=8)
    learning_style:Literal['reading','video','hands-on','mixed']
    current_skills:str=Field(default='',max_length=3000)
    resume_report_id:UUID|None=None
    job_match_id:UUID|None=None

class Generate(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    request_id:UUID
    verified_resume_text:str=Field(default='',max_length=20000)
    @field_validator('verified_resume_text')
    @classmethod
    def valid_resume(cls,v):
        if v and len(v)<50:raise ValueError('Resume text must be at least 50 characters')
        return v

class TaskUpdate(BaseModel):
    model_config=ConfigDict(extra='forbid')
    completed:bool

class MentorQuestion(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    question:str=Field(min_length=3,max_length=3000)

class Skill(BaseModel):
    name:str=Field(min_length=1,max_length=120)
    category:Literal['existing','missing','improve']
    level:Literal['beginner','intermediate','advanced']
    priority:Literal['high','medium','low']
    estimated_hours:float=Field(ge=0,le=1000,allow_inf_nan=False)
    rationale:str=Field(min_length=1,max_length=400)

class PlanTask(BaseModel):
    day:int=Field(ge=1,le=7)
    title:str=Field(min_length=1,max_length=150)
    description:str=Field(min_length=1,max_length=500)
    estimated_minutes:int=Field(ge=5,le=480)
    difficulty:Literal['beginner','intermediate','advanced']
    skill:str=Field(min_length=1,max_length=120)
    resource_ids:list[str]=Field(default_factory=list,max_length=3)

class Week(BaseModel):
    week:int=Field(ge=1,le=8)
    theme:str=Field(min_length=1,max_length=150)
    tasks:list[PlanTask]=Field(min_length=1,max_length=7)

class RoadmapAI(BaseModel):
    summary:str=Field(min_length=1,max_length=800)
    evidence_limitations:str=Field(min_length=1,max_length=800)
    skills:list[Skill]=Field(min_length=1,max_length=20)
    weeks:list[Week]=Field(min_length=1,max_length=8)

class MentorAnswer(BaseModel):
    answer:str=Field(min_length=1,max_length=5000)

from pydantic import BaseModel, ConfigDict, Field, field_validator

class AIQuestion(BaseModel):
    question: str = Field(min_length=5, max_length=1200)
    category: str = Field(min_length=1, max_length=100)

    @field_validator('question', 'category')
    @classmethod
    def non_blank(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('Question fields cannot be blank')
        return value

class QuestionSet(BaseModel):
    questions: list[AIQuestion] = Field(min_length=1, max_length=5)

class Evaluation(BaseModel):
    score: int = Field(ge=0, le=10)
    strengths: list[str] = Field(max_length=8)
    weaknesses: list[str] = Field(max_length=8)
    missing_concepts: list[str] = Field(max_length=8)
    improvement_suggestions: list[str] = Field(max_length=8)
    ideal_answer: str = Field(min_length=1, max_length=6000)
    encouraging_feedback: str = Field(min_length=1, max_length=2000)

    @field_validator('strengths', 'weaknesses', 'missing_concepts', 'improvement_suggestions')
    @classmethod
    def bound_list_text(cls, value):
        if any(not item.strip() or len(item) > 1000 for item in value):
            raise ValueError('Invalid feedback item')
        return value

class ReportNarrative(BaseModel):
    strong_areas: list[str] = Field(max_length=8)
    weak_areas: list[str] = Field(max_length=8)
    technical_analysis: str = Field(min_length=1, max_length=3000)
    communication_feedback: str = Field(min_length=1, max_length=3000)
    recommendations: list[str] = Field(max_length=8)
    practice_roadmap: list[str] = Field(max_length=8)

    @field_validator('strong_areas','weak_areas','recommendations','practice_roadmap')
    @classmethod
    def bound_list_text(cls, value):
        if any(not item.strip() or len(item) > 1000 for item in value):
            raise ValueError('Invalid report item')
        return value

class AnswerSubmit(BaseModel):
    model_config = ConfigDict(extra='forbid')
    answer: str = Field(min_length=1, max_length=5000)

    @field_validator('answer')
    @classmethod
    def not_blank(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('Answer cannot be empty; use Skip instead')
        return value

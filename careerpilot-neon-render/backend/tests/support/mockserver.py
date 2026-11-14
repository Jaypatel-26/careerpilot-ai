"""LOCAL TEST SERVER ONLY: mock AI. Never run or deploy this module in production."""
import time
from app.main import app
from app.services import gemini
from app.schemas.ai_interview import QuestionSet, Evaluation, ReportNarrative
calls={'questions':0,'evaluate':0,'report':0}
def questions(role,focus,difficulty,count,experience,skills):
    calls['questions']+=1;time.sleep(0.6)
    return QuestionSet.model_validate({'questions':[{'question':f'How would you explain concept number {i}?','category':focus} for i in range(1,count+1)]})
def evaluate(role,question,answer):
    calls['evaluate']+=1
    return Evaluation(score=7,strengths=['Clear explanation'],weaknesses=['More detail'],missing_concepts=['Testing'],improvement_suggestions=['Practice examples'],ideal_answer='An illustrative answer.',encouraging_feedback='Keep going!')
def report(role,focus,evaluations):
    calls['report']+=1
    return ReportNarrative(strong_areas=['Clarity'],weak_areas=['Depth'],technical_analysis='Practice testing',communication_feedback='Clear',recommendations=['Practice'],practice_roadmap=['Week 1: basics'])
gemini.questions=questions;gemini.evaluate=evaluate;gemini.report=report
@app.get('/test-counts')
def get_counts(): return calls

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
def resume_analysis(text,job):
    time.sleep(0.3)
    r={'overall_score':75,'ats_score':70,'strengths':['Clear experience'],'weaknesses':['Add detail'],'missing_skills':['Testing'],'missing_sections':['Projects'],'grammar_suggestions':['Use consistent tense'],'project_improvements':['Explain approach'],'experience_suggestions':['Add context'],'education_skills_review':['Clarify education'],'formatting_suggestions':['Use headings'],'action_verbs':['Built'],'measurable_achievement_suggestions':['Add a verified metric'],'bullet_improvements':[{'before':'built accessible user interfaces','after':'Built accessible user interfaces','note':'Verify details'}],'job_match':None}
    if job.strip():r['job_match']={'score':60,'matching_skills':['React'],'missing_skills':['SQL'],'matching_keywords':['React'],'missing_keywords':['SQL'],'requirements_not_covered':['SQL'],'targeted_suggestions':['Explain relevant work'],'project_suggestions':['Practice SQL']}
    return r
gemini.resume_analysis=resume_analysis
# Local browser tests only: fictional jobs never used by production provider.
from app.services import job_provider
def mock_board(token):
    return [job_provider.normalize(token,'Fictional Test Company',{'id':123,'title':'Junior React Developer','location':{'name':'Remote, India'},'content':'<p>We need React, JavaScript and SQL.</p>','absolute_url':'https://example.com/careers/123','updated_at':'2026-11-01T00:00:00Z','first_published':'2026-10-30T00:00:00Z'})]
job_provider._board=mock_board
def mock_job_match(evidence,text,job):
    return {'match_score':71,'matching_skills':['React'],'missing_skills':['SQL'],'important_requirements':['JavaScript'],'requirements_not_evidenced':['SQL'],'improvements':['Verify skills'],'recommended_roles':['Frontend developer'],'evidence_limitations':['Resume report may be incomplete']}
gemini.job_match=mock_job_match

# Fictional test data only; an actual deployment never imports this module.
from app.services import adzuna_provider
def fake_adzuna(page,title,location,limit):
    return {'count':1,'results':[{'id':'998877','title':'React Developer India','company':{'display_name':'Fictional Adzuna Employer'},'location':{'display_name':'Ahmedabad, India'},'description':'React and JavaScript required.','created':'2026-11-01T00:00:00Z','redirect_url':'https://www.adzuna.in/jobs/123'}]}
adzuna_provider._fetch=fake_adzuna

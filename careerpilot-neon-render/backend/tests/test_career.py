from uuid import uuid4
from test_foundation import client,signup,auth
from app.api.ai_interviews import _calls
from app.services import career,gemini
from app.schemas.career import RoadmapAI

GOAL={'role':'Full Stack Developer','skill_level':'beginner','experience':'fresher','daily_hours':2,'weeks':2,'learning_style':'hands-on','current_skills':'HTML, CSS','resume_report_id':None,'job_match_id':None}

def ai_plan(goal,evidence,weeks):
    return {'summary':'Build web skills and projects.','evidence_limitations':'Self-reported skills require verification.',
      'skills':[{'name':'HTML','category':'existing','level':'beginner','priority':'low','estimated_hours':2,'rationale':'Self-reported.'},{'name':'React','category':'missing','level':'intermediate','priority':'high','estimated_hours':20,'rationale':'Useful for the role.'}],
      'weeks':[{'week':i,'theme':'Web skills','tasks':[{'day':d,'title':f'Day {d}','description':'Practice and revise.','estimated_minutes':60,'difficulty':'beginner','skill':'React' if d>1 else 'HTML','resource_ids':['react']} for d in range(1,8)]} for i in range(1,weeks+1)]}

def test_complete_career_flow_and_isolation(client,monkeypatch):
    _calls.clear();monkeypatch.setattr(career,'generate',ai_plan);monkeypatch.setattr(career,'mentor',lambda goal,roadmap,question:'Practice one concept at a time.')
    h=auth(signup(client));h2=auth(signup(client,'two@example.com'))
    assert client.get('/api/v1/career').status_code==401
    assert client.get('/api/v1/career',headers=h).json()['goal'] is None
    assert client.post('/api/v1/career/generate',headers=h,json={'request_id':str(uuid4())}).status_code==404
    assert client.put('/api/v1/career/goal',headers=h,json={**GOAL,'weeks':0}).status_code==422
    assert client.put('/api/v1/career/goal',headers=h,json={**GOAL,'resume_report_id':str(uuid4())}).status_code==404
    assert client.put('/api/v1/career/goal',headers=h,json={**GOAL,'job_match_id':str(uuid4())}).status_code==404
    assert client.put('/api/v1/career/goal',headers=h,json=GOAL).status_code==200
    req={'request_id':str(uuid4()),'verified_resume_text':''}
    r=client.post('/api/v1/career/generate',headers=h,json=req);assert r.status_code==200,r.text
    plan=r.json()['roadmap'];assert len(plan['weeks'])==2 and plan['progress']['total_tasks']==14
    assert plan['weeks'][0]['tasks'][0]['resources'][0]['url']=='https://react.dev/learn'
    tid=plan['weeks'][0]['tasks'][0]['id']
    assert client.get('/api/v1/career',headers=h2).json()['roadmap'] is None
    assert client.patch('/api/v1/career/tasks/'+tid,headers=h2,json={'completed':True}).status_code==404
    assert client.post('/api/v1/career/mentor',headers=h2,json={'question':'Explain HTML'}).status_code==404
    r=client.patch('/api/v1/career/tasks/'+tid,headers=h,json={'completed':True});p=r.json()['roadmap']
    assert p['progress']['completed_tasks']==1 and p['progress']['percent']==7 and p['weeks'][0]['tasks'][0]['completed_at']
    assert client.post('/api/v1/career/generate',headers=h,json=req).json()['roadmap']['weeks'][0]['tasks'][0]['completed'] is True
    assert client.post('/api/v1/career/generate',headers=h,json={**req,'verified_resume_text':'A'*50}).status_code==409
    assert client.patch('/api/v1/career/tasks/'+tid,headers=h,json={'completed':False}).json()['roadmap']['progress']['completed_tasks']==0
    assert client.post('/api/v1/career/mentor',headers=h,json={'question':'Explain HTML'}).json()['answer'].startswith('Practice')
    assert client.put('/api/v1/career/goal',headers=h,json={**GOAL,'role':'Data Analyst'}).json()['roadmap']['outdated']
    new=client.post('/api/v1/career/generate',headers=h,json={'request_id':str(uuid4())}).json()['roadmap']
    assert not new['outdated'] and new['progress']['completed_tasks']==0 and new['weeks'][0]['tasks'][0]['id']!=tid
    assert client.patch('/api/v1/career/tasks/'+tid,headers=h,json={'completed':True}).status_code==404
    assert client.get('/api/v1/career',headers=h).headers['cache-control']=='no-store'

def test_reference_isolation(client,monkeypatch):
    from test_resume import TEXT,analysis
    _calls.clear();monkeypatch.setattr(gemini,'resume_analysis',lambda text,job:{**analysis(False),'job_match':None})
    h=auth(signup(client));h2=auth(signup(client,'other@example.com'))
    r=client.post('/api/v1/resumes/analyze',headers=h,json={'request_id':str(uuid4()),'resume_text':TEXT});assert r.status_code==200
    rid=r.json()['id']
    assert client.put('/api/v1/career/goal',headers=h2,json={**GOAL,'resume_report_id':rid}).status_code==404
    assert client.put('/api/v1/career/goal',headers=h,json={**GOAL,'resume_report_id':rid}).status_code==200
    def check(goal,evidence,weeks):
        assert evidence['resume_report'] is not None and evidence['verified_resume_text']=='A'*50
        return ai_plan(goal,evidence,weeks)
    monkeypatch.setattr(career,'generate',check)
    result=client.post('/api/v1/career/generate',headers=h,json={'request_id':str(uuid4()),'verified_resume_text':'A'*50})
    assert result.status_code==200 and 'A'*50 not in result.text

def test_invalid_ai_structures_and_no_invented_links(monkeypatch):
    sample=ai_plan(GOAL,{},2);sample['weeks'][0]['tasks'][0]['resource_ids']=['react','https://fake.example']
    monkeypatch.setattr(career,'_generate',lambda *args,**kw:RoadmapAI.model_validate(sample))
    result=career.generate(GOAL,{},2);assert result['weeks'][0]['tasks'][0]['resource_ids']==['react']
    sample['weeks'][1]['tasks'].pop()
    import pytest
    with pytest.raises(gemini.AIServiceError):career.generate(GOAL,{},2)

def test_failure_preserves_existing_plan(client,monkeypatch):
    _calls.clear();h=auth(signup(client));client.put('/api/v1/career/goal',headers=h,json=GOAL)
    monkeypatch.setattr(career,'generate',ai_plan)
    before=client.post('/api/v1/career/generate',headers=h,json={'request_id':str(uuid4())}).json()
    def fail(*args):raise gemini.AIServiceError(503,'AI temporarily unavailable.')
    monkeypatch.setattr(career,'generate',fail)
    assert client.post('/api/v1/career/generate',headers=h,json={'request_id':str(uuid4())}).status_code==503
    assert client.get('/api/v1/career',headers=h).json()['roadmap']==before['roadmap']

def test_job_match_reuse_and_isolation(client,monkeypatch):
    from app.models import JobMatchReport,User
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    _calls.clear();h=auth(signup(client));h2=auth(signup(client,'other@example.com'))
    with Session(client.engine) as db:
        user=db.scalar(select(User).where(User.email=='one@example.com'))
        match=JobMatchReport(user_id=user.id,request_id=uuid4(),input_hash='0'*64,job_key='gitlab~42',job={'title':'Engineer','description':'Requires Python','company':'Example'},report={'missing_skills':['Python']},model_name='test')
        db.add(match);db.commit();mid=str(match.id)
    assert client.put('/api/v1/career/goal',headers=h2,json={**GOAL,'job_match_id':mid}).status_code==404
    assert client.put('/api/v1/career/goal',headers=h,json={**GOAL,'job_match_id':mid}).status_code==200
    def check(goal,evidence,weeks):
        assert evidence['job_match']['job_description']=='Requires Python'
        assert evidence['job_match']['ai_match']['missing_skills']==['Python']
        return ai_plan(goal,evidence,weeks)
    monkeypatch.setattr(career,'generate',check)
    assert client.post('/api/v1/career/generate',headers=h,json={'request_id':str(uuid4())}).status_code==200

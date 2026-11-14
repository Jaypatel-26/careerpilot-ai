import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4
import pytest
from sqlalchemy import text, create_engine
from app.api.ai_interviews import _calls
from app.services import gemini
from app.schemas.ai_interview import QuestionSet, Evaluation, ReportNarrative
from test_foundation import client, signup, auth, PAYLOAD

@pytest.fixture(autouse=True)
def clear_ai_limits():
    _calls.clear()
    yield
    _calls.clear()

@pytest.fixture
def fake_ai(monkeypatch):
    calls = {'questions':0, 'evaluate':0, 'report':0}
    def questions(role, focus, difficulty, count, experience, skills):
        calls['questions'] += 1
        return QuestionSet.model_validate({'questions':[{'question':f'Question number {i}?','category':focus} for i in range(1,count+1)]})
    def evaluate(role, question, answer):
        calls['evaluate'] += 1
        return Evaluation(score=7, strengths=['Clear'], weaknesses=['Depth'], missing_concepts=['Testing'], improvement_suggestions=['Practice'], ideal_answer='A suitable answer', encouraging_feedback='Keep practicing!')
    def report(role, focus, evaluations):
        calls['report'] += 1
        return ReportNarrative(strong_areas=['Clear'], weak_areas=['Depth'], technical_analysis='Review tests', communication_feedback='Clear', recommendations=['Practice'], practice_roadmap=['Week 1: basics'])
    monkeypatch.setattr(gemini,'questions',questions)
    monkeypatch.setattr(gemini,'evaluate',evaluate)
    monkeypatch.setattr(gemini,'report',report)
    return calls


def test_complete_real_interview_and_idempotent_retries(client, fake_ai):
    h = auth(signup(client))
    create = client.post('/api/v1/interviews', headers=h, json={**PAYLOAD,'question_focus':'situational','experience_level':'Fresher','skills':'Python'})
    assert create.status_code == 201
    sid = create.json()['id']; root = f'/api/v1/interviews/{sid}'
    assert client.post(root+'/complete', headers=h).status_code == 409
    first = client.post(root+'/start', headers=h)
    assert first.status_code == 200 and first.json()['total'] == 3
    assert client.post(root+'/start', headers=h).json()['current'] == first.json()['current']
    assert fake_ai['questions'] == 1
    q = first.json()['current']['id']; base = root+f'/questions/{q}'
    assert client.post(base+'/answer', headers=h,json={'answer':'  '}).status_code == 422
    assert client.post(base+'/answer',headers=h,json={'answer':'I explain my approach.'}).status_code == 200
    assert client.post(base+'/answer',headers=h,json={'answer':'I explain my approach.'}).status_code == 200
    assert client.post(base+'/answer',headers=h,json={'answer':'Different answer'}).status_code == 409
    assert client.get(root+'/current', headers=h).json()['current']['answer_saved']
    assert client.post(base+'/evaluate', headers=h).json()['score'] == 7
    assert client.post(base+'/evaluate', headers=h).json()['score'] == 7
    assert fake_ai['evaluate'] == 1
    q2=client.get(root+'/current',headers=h).json()['current']['id']
    assert client.post(root+f'/questions/{q2}/skip', headers=h).status_code == 200
    assert client.post(root+f'/questions/{q2}/skip', headers=h).status_code == 200
    q3=client.get(root+'/current',headers=h).json()['current']['id']
    assert client.post(root+f'/questions/{q3}/answer',headers=h,json={'answer':'Another complete answer.'}).status_code == 200
    assert client.post(root+'/complete',headers=h).status_code == 409
    assert client.post(root+f'/questions/{q3}/evaluate',headers=h).status_code == 200
    assert client.get(root+'/current',headers=h).json()['ready_to_complete']
    report = client.post(root+'/complete',headers=h)
    assert report.status_code == 200
    assert report.json()['overall_score'] == 4.67
    assert report.json()['answered_questions'] == 2 and report.json()['skipped_questions'] == 1
    assert client.post(root+'/complete',headers=h).json() == report.json()
    assert client.get(root+'/report',headers=h).json() == report.json()
    assert fake_ai['report'] == 1
    assert client.get('/api/v1/interviews',headers=h).json()[0]['status'] == 'completed'


def test_private_ownership_and_auth(client, fake_ai):
    a,b=auth(signup(client)),auth(signup(client,'two@example.com'))
    sid=client.post('/api/v1/interviews',headers=a,json=PAYLOAD).json()['id'];root=f'/api/v1/interviews/{sid}'
    q=client.post(root+'/start',headers=a).json()['current']['id']
    for method,path in [('get','/current'),('post','/start'),('post','/complete'),('get','/report'),('post',f'/questions/{q}/skip'),('post',f'/questions/{q}/evaluate')]:
        assert getattr(client,method)(root+path, headers=b).status_code == 404
        assert getattr(client,method)(root+path).status_code == 401
    assert client.post(root+f'/questions/{q}/answer',headers=b,json={'answer':'hello'}).status_code == 404
    assert client.get(root+'/current',headers=b).status_code == 404


def test_provider_error_preserves_saved_answer_and_retry(client, fake_ai, monkeypatch):
    h=auth(signup(client)); sid=client.post('/api/v1/interviews',headers=h,json=PAYLOAD).json()['id']; root=f'/api/v1/interviews/{sid}'
    normal=gemini.questions
    def fail(*args): raise gemini.AIServiceError(429,'AI quota reached',60)
    monkeypatch.setattr(gemini,'questions',fail)
    response=client.post(root+'/start',headers=h)
    assert response.status_code==429 and response.headers['retry-after']=='60'
    assert client.get(root,headers=h).json()['status']=='draft'
    monkeypatch.setattr(gemini,'questions',normal)
    q=client.post(root+'/start',headers=h).json()['current']['id']; path=root+f'/questions/{q}'
    client.post(path+'/answer',headers=h,json={'answer':'This is a useful answer'})
    normal_eval=gemini.evaluate; monkeypatch.setattr(gemini,'evaluate',fail)
    assert client.post(path+'/evaluate',headers=h).status_code==429
    assert client.get(root+'/current',headers=h).json()['current']['answer_saved']
    monkeypatch.setattr(gemini,'evaluate',normal_eval)
    assert client.post(path+'/evaluate',headers=h).status_code==200


def test_skipping_everything_does_not_call_report_ai(client, fake_ai):
    h=auth(signup(client)); sid=client.post('/api/v1/interviews',headers=h,json={**PAYLOAD,'question_count':1}).json()['id']; root=f'/api/v1/interviews/{sid}'
    q=client.post(root+'/start',headers=h).json()['current']['id']
    assert client.post(root+f'/questions/{q}/skip',headers=h).status_code==200
    report=client.post(root+'/complete',headers=h).json()
    assert report['overall_score']==0 and report['answered_questions']==0
    assert fake_ai['report']==0


def test_ai_limit_and_invalid_question_order(client, fake_ai):
    h=auth(signup(client)); sid=client.post('/api/v1/interviews',headers=h,json={**PAYLOAD,'question_count':6}).json()['id']
    assert client.post(f'/api/v1/interviews/{sid}/start',headers=h).status_code==422
    assert fake_ai['questions']==0


def test_adapter_safe_json_and_error_mapping(monkeypatch):
    from app.core.config import get_settings
    from types import SimpleNamespace
    from google.genai import errors
    monkeypatch.setenv('GEMINI_API_KEY','test-key-do-not-use');get_settings.cache_clear()
    class FakeClient:
        def __init__(self,**kwargs): self.models=self
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def generate_content(self,**kwargs): return SimpleNamespace(text='not-json')
    monkeypatch.setattr(gemini.genai,'Client',FakeClient)
    with pytest.raises(gemini.AIServiceError) as err:
        gemini.questions('Developer','technical','beginner',1,'Fresher','')
    assert err.value.status_code==502
    def quota(self,**kwargs): raise errors.ClientError(429, {'error':{'code':429,'message':'secret'}})
    monkeypatch.setattr(FakeClient,'generate_content',quota)
    with pytest.raises(gemini.AIServiceError) as err:
        gemini.questions('Developer','technical','beginner',1,'Fresher','')
    assert err.value.status_code==429 and 'secret' not in str(err.value)
    monkeypatch.setenv('GEMINI_API_KEY','');get_settings.cache_clear()
    with pytest.raises(gemini.AIServiceError) as err: gemini.questions('Dev','technical','beginner',1,'Fresher','')
    assert err.value.status_code==503
    get_settings.cache_clear()


def test_ai_migration_preserves_existing_draft(tmp_path):
    backend=Path(__file__).resolve().parents[1];url=f"sqlite:///{tmp_path / 'migration.db'}";env=dict(os.environ,DATABASE_URL=url)
    def migrate(version): subprocess.run([sys.executable,'-m','alembic','upgrade',version],cwd=backend,env=env,check=True,capture_output=True)
    migrate('6e7c2a9d3011');engine=create_engine(url); uid,sid=uuid4().hex,uuid4().hex
    with engine.begin() as db:
        db.execute(text("INSERT INTO users (id,email,full_name,password_hash,created_at) VALUES (:id,'one@example.com','User','hash','2025-01-01')"),{'id':uid})
        db.execute(text("INSERT INTO interview_sessions (id,user_id,target_role,interview_type,difficulty,question_count,status,created_at,updated_at) VALUES (:id,:uid,'Saved','technical','beginner',3,'draft','2025-01-01','2025-01-01')"),{'id':sid,'uid':uid})
    migrate('head')
    with engine.connect() as db: assert db.execute(text('SELECT target_role,skills FROM interview_sessions WHERE id=:id'),{'id':sid}).one()==('Saved',None)
    engine.dispose()


def test_adapter_success_uses_structured_output_and_bounds(monkeypatch):
    from types import SimpleNamespace
    from app.core.config import get_settings
    monkeypatch.setenv('GEMINI_API_KEY','fake-key');get_settings.cache_clear()
    seen={}
    class FakeClient:
        def __init__(self,**kwargs): seen['client']=kwargs;self.models=self
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def generate_content(self,**kwargs):
            seen['request']=kwargs
            return SimpleNamespace(text='{"questions":[{"question":"Explain a key concept?","category":"technical"}]}')
    monkeypatch.setattr(gemini.genai,'Client',FakeClient)
    result=gemini.questions('Developer','technical','beginner',1,'Fresher','Python')
    assert result.questions[0].question=='Explain a key concept?'
    assert seen['client']['http_options'].timeout==30000
    assert seen['client']['http_options'].retry_options.attempts==1
    assert seen['request']['config'].response_mime_type=='application/json'
    assert seen['request']['config'].response_json_schema is not None
    assert 'fake-key' not in seen['request']['contents']
    get_settings.cache_clear()


def test_rate_limit_blocks_before_provider(client, fake_ai):
    h=auth(signup(client)); sid=client.post('/api/v1/interviews',headers=h,json=PAYLOAD).json()['id']
    user_id=client.get('/api/v1/auth/me',headers=h).json()['id']
    from time import monotonic
    _calls[user_id].extend([monotonic()]*30)
    r=client.post(f'/api/v1/interviews/{sid}/start',headers=h)
    assert r.status_code==429 and fake_ai['questions']==0

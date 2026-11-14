import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session
from app.models import InterviewAnswer
from test_foundation import client, signup, auth, PAYLOAD
from test_ai_interviews import fake_ai, clear_ai_limits


def test_voice_and_text_are_separate_owned_and_persisted(client, fake_ai):
    a, b = auth(signup(client)), auth(signup(client, 'another@example.com'))
    voice=client.post('/api/v1/interviews',headers=a,json={**PAYLOAD,'mode':'voice'})
    text_session=client.post('/api/v1/interviews',headers=a,json=PAYLOAD)
    assert voice.status_code==201 and voice.json()['mode']=='voice'
    assert text_session.json()['mode']=='text'
    assert client.post('/api/v1/interviews',headers=a,json={**PAYLOAD,'mode':'audio-file'}).status_code==422
    sid=voice.json()['id'];root=f'/api/v1/interviews/{sid}'
    assert client.post(root+'/start',headers=b).status_code==404
    assert client.post(root+'/end',headers=b).status_code==404
    assert client.get(root+'/report',headers=b).status_code==404
    current=client.post(root+'/start',headers=a).json();assert current['mode']=='voice'
    q=current['current']['id'];path=root+f'/questions/{q}'
    assert client.post(path+'/answer',headers=a,json={'answer':'My spoken transcript, edited.','input_mode':'voice'}).status_code==200
    with Session(client.engine) as db:
        saved=db.scalar(select(InterviewAnswer))
        assert saved.input_mode=='voice' and saved.transcript=='My spoken transcript, edited.'
    assert client.get(root+'/current',headers=a).json()['current']['answer']=='My spoken transcript, edited.'
    assert client.post(path+'/evaluate',headers=a).json()['score']==7
    for _ in range(2):
        q=client.get(root+'/current',headers=a).json()['current']['id']
        assert client.post(root+f'/questions/{q}/skip',headers=a).status_code==200
    report=client.post(root+'/complete',headers=a)
    assert report.status_code==200 and report.json()['answered_questions']==1
    assert client.get(root+'/report',headers=a).json()==report.json()
    assert client.get(root+'/current',headers=b).status_code==404
    assert client.get(root+'/current').status_code==401
    assert {row['mode'] for row in client.get('/api/v1/interviews',headers=a).json()}=={'text','voice'}


def test_voice_manual_fallback_and_end_preserve_saved_data(client, fake_ai):
    h=auth(signup(client));sid=client.post('/api/v1/interviews',headers=h,json={**PAYLOAD,'mode':'voice'}).json()['id'];root=f'/api/v1/interviews/{sid}'
    q=client.post(root+'/start',headers=h).json()['current']['id'];path=root+f'/questions/{q}'
    assert client.post(path+'/answer',headers=h,json={'answer':'Typed fallback answer'}).status_code==200
    with Session(client.engine) as db: assert db.scalar(select(InterviewAnswer)).input_mode=='text'
    assert client.post(root+'/end',headers=h).json()=={'status':'abandoned'}
    assert client.post(root+'/end',headers=h).status_code==200
    assert client.get(root,headers=h).json()['status']=='abandoned'
    assert client.get(root+'/current',headers=h).json()['current']['answer']=='Typed fallback answer'
    assert client.post(path+'/evaluate',headers=h).status_code==409
    assert client.post(root+'/complete',headers=h).status_code==409
    assert client.get(root+'/report',headers=h).status_code==404


def test_text_session_rejects_voice_claim_and_is_not_ended_by_voice_api(client,fake_ai):
    h=auth(signup(client));sid=client.post('/api/v1/interviews',headers=h,json=PAYLOAD).json()['id'];root=f'/api/v1/interviews/{sid}'
    q=client.post(root+'/start',headers=h).json()['current']['id'];path=root+f'/questions/{q}'
    assert client.post(path+'/answer',headers=h,json={'answer':'A text answer','input_mode':'voice'}).status_code==422
    assert client.post(root+'/end',headers=h).status_code==409
    assert client.post(path+'/answer',headers=h,json={'answer':'A text answer'}).status_code==200
    assert client.post(path+'/evaluate',headers=h).status_code==200


def test_migration_existing_text_report_and_answers_remain(tmp_path):
    backend=Path(__file__).resolve().parents[1];url=f"sqlite:///{tmp_path / 'voice.db'}";env=dict(os.environ,DATABASE_URL=url)
    def migrate(rev):subprocess.run([sys.executable,'-m','alembic','upgrade',rev],cwd=backend,env=env,check=True,capture_output=True)
    migrate('9f0a2c7d842e');engine=create_engine(url); uid,sid,qid,aid,rid=[uuid4().hex for _ in range(5)]
    with engine.begin() as c:
        c.execute(text("INSERT INTO users (id,email,full_name,password_hash,created_at) VALUES (:id,'old@example.com','Existing','hash','2025-01-01')"),{'id':uid})
        c.execute(text("INSERT INTO interview_sessions (id,user_id,target_role,interview_type,difficulty,question_count,status,created_at,updated_at) VALUES (:id,:uid,'Existing role','technical','beginner',1,'completed','2025-01-01','2025-01-01')"),{'id':sid,'uid':uid})
        c.execute(text("INSERT INTO interview_questions (id,session_id,position,question_text,created_at) VALUES (:id,:sid,1,'Old question','2025-01-01')"),{'id':qid,'sid':sid})
        c.execute(text("INSERT INTO interview_answers (id,question_id,transcript,input_mode,status,submitted_at) VALUES (:id,:qid,'Old answer','text','submitted','2025-01-01')"),{'id':aid,'qid':qid})
        c.execute(text("INSERT INTO interview_reports (id,session_id,overall_score,summary,created_at) VALUES (:id,:sid,70,'Old report','2025-01-01')"),{'id':rid,'sid':sid})
    migrate('head')
    with engine.connect() as c:
        assert c.execute(text('SELECT target_role,mode,status FROM interview_sessions WHERE id=:sid'),{'sid':sid}).one()==('Existing role','text','completed')
        assert c.execute(text('SELECT transcript FROM interview_answers WHERE id=:id'),{'id':aid}).scalar_one()=='Old answer'
        assert c.execute(text('SELECT summary FROM interview_reports WHERE id=:id'),{'id':rid}).scalar_one()=='Old report'
    engine.dispose()


def test_voice_answer_survives_ai_failure_and_retries_without_audio(client,fake_ai,monkeypatch):
    from app.services import gemini
    h=auth(signup(client));sid=client.post('/api/v1/interviews',headers=h,json={**PAYLOAD,'mode':'voice'}).json()['id'];root=f'/api/v1/interviews/{sid}'
    q=client.post(root+'/start',headers=h).json()['current']['id'];path=root+f'/questions/{q}'
    assert client.post(path+'/answer',headers=h,json={'answer':'This is a transcript.','input_mode':'voice','audio':'not permitted'}).status_code==422
    assert client.post(path+'/answer',headers=h,json={'answer':'This is a transcript.','input_mode':'voice'}).status_code==200
    original=gemini.evaluate
    def fail(*args): raise gemini.AIServiceError(503,'AI temporarily unavailable',30)
    monkeypatch.setattr(gemini,'evaluate',fail)
    assert client.post(path+'/evaluate',headers=h).status_code==503
    assert client.get(root+'/current',headers=h).json()['current']['answer']=='This is a transcript.'
    monkeypatch.setattr(gemini,'evaluate',original)
    assert client.post(path+'/evaluate',headers=h).status_code==200

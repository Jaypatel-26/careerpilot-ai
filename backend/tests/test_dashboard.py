from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_foundation import client,signup,auth
from app.models import User,InterviewSession,InterviewReport,ResumeReport,SavedJob,JobMatchReport,CareerPlan


def test_dashboard_empty_and_private_aggregate(client):
    a=signup(client,'alice@example.com');b=signup(client,'bob@example.com');ha,hb=auth(a),auth(b)
    assert client.get('/api/v1/dashboard').status_code==401
    r=client.get('/api/v1/dashboard',headers=ha);assert r.status_code==200 and r.headers['cache-control']=='no-store'
    assert r.json()['name']=='Test User' and r.json()['interviews']==0 and r.json()['average_score'] is None and r.json()['career'] is None
    with Session(client.engine) as db:
        alice=db.scalar(select(User).where(User.email=='alice@example.com'));bob=db.scalar(select(User).where(User.email=='bob@example.com'))
        alice.target_role='Data Analyst'
        i=InterviewSession(user_id=alice.id,target_role='Data Analyst',interview_type='technical',difficulty='beginner',question_count=3,status='completed',mode='text')
        j=InterviewSession(user_id=bob.id,target_role='Private Bob Role',interview_type='technical',difficulty='beginner',question_count=3,status='completed',mode='voice')
        db.add_all([i,j]);db.flush()
        db.add_all([InterviewReport(session_id=i.id,overall_score=70),InterviewReport(session_id=j.id,overall_score=10),
          ResumeReport(user_id=alice.id,request_id=uuid4(),input_hash='0'*64,report={},model_name='test'),
          SavedJob(user_id=alice.id,job_key='gitlab~1',job={'title':'Example'}),
          SavedJob(user_id=bob.id,job_key='gitlab~2',job={'title':'Bob private job'}),
          JobMatchReport(user_id=alice.id,request_id=uuid4(),input_hash='0'*64,job_key='gitlab~1',job={},report={},model_name='test')])
        goal={'role':'Data Analyst'}
        plan={'goal_snapshot':goal,'skills':[{'name':'SQL'}], 'weeks':[{'week':1,'tasks':[{'id':str(uuid4()),'day':1,'title':'Practice SQL','skill':'SQL','completed':True,'resource_ids':[]}]}]}
        db.add(CareerPlan(user_id=alice.id,goal=goal,roadmap=plan));db.commit()
    x=client.get('/api/v1/dashboard',headers=ha).json();y=client.get('/api/v1/dashboard',headers=hb).json()
    assert (x['interviews'],x['completed_interviews'],x['average_score'],x['saved_jobs'],x['resume_reports'],x['job_matches'])==(1,1,70,1,1,1)
    assert x['career']['percent']==100 and x['profile_role']=='Data Analyst' and x['recent_scores'][0]['score']==70
    assert y['average_score']==10 and y['resume_reports']==0 and y['job_matches']==0 and y['career'] is None
    assert 'Private Bob Role' not in str(x) and 'Data Analyst' not in str(y)

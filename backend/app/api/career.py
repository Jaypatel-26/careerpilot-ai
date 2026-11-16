"""One private career plan per account. AI is advisory, never proof of skills."""
import copy
import hashlib
import json
from datetime import datetime,timezone
from uuid import UUID,uuid4
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.ai_interviews import provider_call
from app.core.security import current_user
from app.db.session import get_db
from app.models import CareerPlan,User,ResumeReport,JobMatchReport
from app.schemas.career import Goal,Generate,TaskUpdate,MentorQuestion
from app.services import career

router=APIRouter(prefix='/career',tags=['Career roadmap'])

def owned(db,user_id,lock=False):
    q=select(CareerPlan).where(CareerPlan.user_id==user_id)
    if lock:q=q.with_for_update()
    return db.scalar(q)

def refs(db,user_id,goal):
    resume=match=None
    if goal.get('resume_report_id'):
        resume=db.scalar(select(ResumeReport).where(ResumeReport.id==UUID(goal['resume_report_id']),ResumeReport.user_id==user_id))
        if not resume:raise HTTPException(404,'Resume report not found. Choose another report or clear the selection.')
    if goal.get('job_match_id'):
        match=db.scalar(select(JobMatchReport).where(JobMatchReport.id==UUID(goal['job_match_id']),JobMatchReport.user_id==user_id))
        if not match:raise HTTPException(404,'Job match not found. Choose another match or clear the selection.')
    return resume,match

def response(row):
    if not row:return {'goal':None,'roadmap':None,'updated_at':None}
    plan=copy.deepcopy(row.roadmap)
    if plan:
        for w in plan['weeks']:
            for t in w['tasks']:
                t['resources']=[career.RESOURCES[x] for x in t.pop('resource_ids',[]) if x in career.RESOURCES]
        tasks=[t for w in plan['weeks'] for t in w['tasks']]
        done=sum(bool(t['completed']) for t in tasks)
        skills=plan['skills']; completed=[]
        for skill in skills:
            relevant=[t for t in tasks if t['skill'].casefold()==skill['name'].casefold()]
            if relevant and all(t['completed'] for t in relevant):completed.append(skill['name'])
        plan['progress']={'completed_tasks':done,'total_tasks':len(tasks),'percent':round(done*100/len(tasks)) if tasks else 0,
            'total_skills':len(skills),'completed_skills':len(completed),'remaining_skills':len(skills)-len(completed),
            'next_task':next(({'week':w['week'],'day':t['day'],'title':t['title']} for w in plan['weeks'] for t in w['tasks'] if not t['completed']),None),
            'weeks':[{'week':w['week'],'done':sum(t['completed'] for t in w['tasks']),'total':len(w['tasks'])} for w in plan['weeks']]}
        plan['outdated']=plan['goal_snapshot']!=row.goal
    return {'goal':row.goal,'roadmap':plan,'updated_at':row.updated_at}

@router.get('')
def get(user_id:UUID=Depends(current_user),db:Session=Depends(get_db)):
    return response(owned(db,user_id))

@router.put('/goal')
def save_goal(payload:Goal,user_id:UUID=Depends(current_user),db:Session=Depends(get_db)):
    goal=payload.model_dump(mode='json');refs(db,user_id,goal)
    db.scalar(select(User).where(User.id==user_id).with_for_update())
    row=owned(db,user_id,True)
    if not row:row=CareerPlan(user_id=user_id,goal=goal);db.add(row)
    else:row.goal=goal
    db.commit();db.refresh(row);return response(row)

@router.post('/generate')
def generate(payload:Generate,user_id:UUID=Depends(current_user),db:Session=Depends(get_db)):
    db.scalar(select(User).where(User.id==user_id).with_for_update())
    row=owned(db,user_id,True)
    if not row:raise HTTPException(404,'Save your learning goal first.')
    fingerprint=hashlib.sha256((json.dumps(row.goal,sort_keys=True)+'\0'+payload.verified_resume_text).encode()).hexdigest()
    if row.request_id==payload.request_id:
        if row.input_hash!=fingerprint:raise HTTPException(409,'This request ID was used with different input.')
        return response(row)
    resume,match=refs(db,user_id,row.goal)
    evidence={'verified_resume_text':payload.verified_resume_text,
      'resume_report':{'strengths':resume.report.get('strengths',[]),'quoted_before_bullets':[x.get('before','') for x in resume.report.get('bullet_improvements',[]) if isinstance(x,dict)]} if resume else None,
      'job_match':{'job_title':match.job.get('title'), 'job_description':match.job.get('description','')[:10000], 'ai_match':match.report} if match else None}
    result=provider_call(user_id,career.generate,row.goal,evidence,row.goal['weeks'])
    for w in result['weeks']:
        for t in w['tasks']:t.update(id=str(uuid4()),completed=False,completed_at=None)
    result['goal_snapshot']=copy.deepcopy(row.goal);result['generated_at']=datetime.now(timezone.utc).isoformat()
    row.roadmap=result;row.request_id=payload.request_id;row.input_hash=fingerprint
    db.commit();db.refresh(row);return response(row)

@router.patch('/tasks/{task_id}')
def task(task_id:UUID,payload:TaskUpdate,user_id:UUID=Depends(current_user),db:Session=Depends(get_db)):
    row=owned(db,user_id,True)
    if not row or not row.roadmap:raise HTTPException(404,'Roadmap task not found.')
    plan=copy.deepcopy(row.roadmap)
    found=next((t for w in plan['weeks'] for t in w['tasks'] if t['id']==str(task_id)),None)
    if found is None:raise HTTPException(404,'Roadmap task not found.')
    if found['completed']!=payload.completed:
        found['completed']=payload.completed;found['completed_at']=datetime.now(timezone.utc).isoformat() if payload.completed else None
        row.roadmap=plan;db.commit();db.refresh(row)
    return response(row)

@router.post('/mentor')
def mentor(payload:MentorQuestion,user_id:UUID=Depends(current_user),db:Session=Depends(get_db)):
    row=owned(db,user_id)
    if not row or not row.roadmap:raise HTTPException(404,'Generate a roadmap before asking the mentor.')
    answer=provider_call(user_id,career.mentor,row.goal,row.roadmap,payload.question)
    return {'answer':answer}

"""Private account dashboard, calculated exclusively from owned records."""
from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from app.core.security import current_user
from app.db.session import get_db
from app.models import User,InterviewSession,InterviewReport,ResumeReport,SavedJob,JobMatchReport,CareerPlan
from app.api.career import response as career_response

router=APIRouter(prefix='/dashboard',tags=['Account dashboard'])

@router.get('')
def summary(user_id:UUID=Depends(current_user),db:Session=Depends(get_db)):
    user=db.get(User,user_id)
    count=lambda model:db.scalar(select(func.count()).select_from(model).where(model.user_id==user_id)) or 0
    interview_count=count(InterviewSession)
    completed=db.scalar(select(func.count()).select_from(InterviewSession).where(InterviewSession.user_id==user_id,InterviewSession.status=='completed')) or 0
    score_query=select(func.avg(InterviewReport.overall_score)).join(InterviewSession,InterviewReport.session_id==InterviewSession.id).where(InterviewSession.user_id==user_id,InterviewReport.overall_score.is_not(None))
    average=db.scalar(score_query)
    sessions=list(db.scalars(select(InterviewSession).where(InterviewSession.user_id==user_id).order_by(InterviewSession.created_at.desc(),InterviewSession.id.desc()).limit(5)))
    scores=list(db.execute(select(InterviewReport.overall_score,InterviewReport.created_at).join(InterviewSession,InterviewReport.session_id==InterviewSession.id).where(InterviewSession.user_id==user_id,InterviewReport.overall_score.is_not(None)).order_by(InterviewReport.created_at.desc(),InterviewReport.id.desc()).limit(10)))
    plan=db.scalar(select(CareerPlan).where(CareerPlan.user_id==user_id))
    roadmap=career_response(plan)['roadmap'] if plan and plan.roadmap else None
    return {'name':user.full_name,'email':user.email,'profile_role':user.target_role or None,
        'interviews':interview_count,'completed_interviews':completed,'average_score':round(float(average),1) if average is not None else None,
        'resume_reports':count(ResumeReport),'saved_jobs':count(SavedJob),'job_matches':count(JobMatchReport),
        'recent_interviews':[{'id':str(x.id),'role':x.target_role,'status':x.status,'mode':x.mode,'created_at':x.created_at} for x in sessions],
        'recent_scores':[{'score':score,'date':date} for score,date in reversed(scores)],
        'career':{'target_role':roadmap['goal_snapshot']['role'],'percent':roadmap['progress']['percent'],'completed_tasks':roadmap['progress']['completed_tasks'],'total_tasks':roadmap['progress']['total_tasks'],'next_task':roadmap['progress']['next_task'],'outdated':roadmap['outdated']} if roadmap else None,
        'goal_role':plan.goal.get('role') if plan else None}

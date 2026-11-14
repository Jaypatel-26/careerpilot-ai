"""Configured live job feed and account-owned saved jobs and matches."""
from uuid import UUID
import hashlib
import re
from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.ai_interviews import provider_call
from app.core.config import get_settings
from app.core.security import current_user
from app.db.session import get_db
from app.models import User,ResumeReport,SavedJob,JobMatchReport
from app.schemas.job import SaveJobRequest,JobMatchRequest
from app.services import job_provider,adzuna_provider,gemini

router=APIRouter(prefix='/jobs',tags=['Job matching'])
def resolve_job(key,db):
    return adzuna_provider.get_job(db,key) if key.startswith('adzuna~') else job_provider.get_job(key)
def data(row):
    d={'id':row.id,'job':row.job,'created_at':row.created_at}
    if isinstance(row,JobMatchReport):d.update(report=row.report,resume_report_id=row.resume_report_id)
    return d

@router.get('/search')
def search(title:str=Query('',max_length=100),company:str=Query('',max_length=100),location:str=Query('',max_length=100),
           workplace:str=Query('',pattern='^(|remote|hybrid|onsite)$'),experience:str=Query('',pattern='^(|internship|entry|mid|senior)$'),
           skills:str=Query('',max_length=150),offset:int=Query(0,ge=0,le=15000),limit:int=Query(20,ge=1,le=50),source:str=Query('greenhouse',pattern='^(greenhouse|adzuna|all)$'),user_id:UUID=Depends(current_user),db:Session=Depends(get_db)):
    if source=='adzuna':return adzuna_provider.search(db,user_id,title,company,location,workplace,experience,skills,offset,limit)
    if source=='all':
        feeds=[];warnings=[]
        for name in ('greenhouse','adzuna'):
            try:
                part=search(title,company,location,workplace,experience,skills,offset,limit,name,user_id,db)
                feeds.append(part);warnings.extend(part['warnings'])
            except HTTPException as exc:
                warnings.append(('Greenhouse' if name=='greenhouse' else 'Adzuna')+': '+str(exc.detail))
        if not feeds:raise HTTPException(503,'Job sources are unavailable. Please try again later.')
        # Each source is independently paged. Adzuna count is pre-filter; do not sum these into a global total.
        return {'items':[j for feed in feeds for j in feed['items']], 'total':max((f['total'] for f in feeds),default=0),
            'offset':offset,'limit':limit,'source':'Combined','warnings':warnings,
            'source_counts':{f['source']:f['total'] for f in feeds}}
    items,warnings=job_provider.feed();terms=[x.strip().casefold() for x in skills.split(',') if x.strip()][:10]
    def accepts(j):
        return (title.casefold().strip() in j['title'].casefold() and company.casefold().strip() in j['company'].casefold()
            and location.casefold().strip() in j['location'].casefold() and (not workplace or j['workplace']==workplace)
            and (not experience or j['experience']==experience) and all(re.search(r'(?<!\w)'+re.escape(t)+r'(?!\w)',j['title']+' '+j['description'],re.I) for t in terms))
    filtered=[j for j in items if accepts(j)];filtered.sort(key=lambda x:x['updated_at'] or '',reverse=True)
    return {'items':[{**j,'description':j['description'][:400]} for j in filtered[offset:offset+limit]],'total':len(filtered),'offset':offset,'limit':limit,'warnings':warnings,'source':'Greenhouse'}

@router.get('/saved')
def saved(user_id:UUID=Depends(current_user),db:Session=Depends(get_db)):
    stmt=select(SavedJob).where(SavedJob.user_id==user_id)
    if not adzuna_provider.configured():stmt=stmt.where(~SavedJob.job_key.startswith('adzuna~'))
    return [data(x) for x in db.scalars(stmt.order_by(SavedJob.created_at.desc()).limit(100))]

@router.post('/saved')
def save(payload:SaveJobRequest,user_id:UUID=Depends(current_user),db:Session=Depends(get_db)):
    job=resolve_job(payload.job_key,db)
    db.scalar(select(User).where(User.id==user_id).with_for_update())
    existing=db.scalar(select(SavedJob).where(SavedJob.user_id==user_id,SavedJob.job_key==payload.job_key))
    if existing:return data(existing)
    row=SavedJob(user_id=user_id,job_key=payload.job_key,job=job);db.add(row);db.commit();db.refresh(row);return data(row)

@router.delete('/saved/{saved_id}',status_code=204)
def remove_saved(saved_id:UUID,user_id:UUID=Depends(current_user),db:Session=Depends(get_db)):
    row=db.scalar(select(SavedJob).where(SavedJob.id==saved_id,SavedJob.user_id==user_id))
    if not row:raise HTTPException(404,'Saved job not found.')
    db.delete(row);db.commit()

@router.get('/matches')
def matches(user_id:UUID=Depends(current_user),db:Session=Depends(get_db)):
    stmt=select(JobMatchReport).where(JobMatchReport.user_id==user_id)
    if not adzuna_provider.configured():stmt=stmt.where(~JobMatchReport.job_key.startswith('adzuna~'))
    return [data(x) for x in db.scalars(stmt.order_by(JobMatchReport.created_at.desc()).limit(100))]

@router.get('/matches/{match_id}')
def get_match(match_id:UUID,user_id:UUID=Depends(current_user),db:Session=Depends(get_db)):
    row=db.scalar(select(JobMatchReport).where(JobMatchReport.id==match_id,JobMatchReport.user_id==user_id))
    if not row or (row.job_key.startswith('adzuna~') and not adzuna_provider.configured()):raise HTTPException(404,'Match report not found.')
    return data(row)

@router.delete('/matches/{match_id}',status_code=204)
def remove_match(match_id:UUID,user_id:UUID=Depends(current_user),db:Session=Depends(get_db)):
    row=db.scalar(select(JobMatchReport).where(JobMatchReport.id==match_id,JobMatchReport.user_id==user_id))
    if not row:raise HTTPException(404,'Match report not found.')
    db.delete(row);db.commit()

@router.post('/match')
def match(payload:JobMatchRequest,user_id:UUID=Depends(current_user),db:Session=Depends(get_db)):
    resume=db.scalar(select(ResumeReport).where(ResumeReport.id==payload.resume_report_id,ResumeReport.user_id==user_id))
    if not resume:raise HTTPException(404,'Resume report not found.')
    text=payload.verified_resume_text.strip()
    if text and len(text)<50:raise HTTPException(422,'If adding resume text, provide at least 50 characters.')
    fp=hashlib.sha256((payload.job_key+'\0'+str(payload.resume_report_id)+'\0'+text).encode()).hexdigest()
    db.scalar(select(User).where(User.id==user_id).with_for_update())
    previous=db.scalar(select(JobMatchReport).where(JobMatchReport.user_id==user_id,JobMatchReport.request_id==payload.request_id))
    if previous:
        if previous.job_key.startswith('adzuna~') and not adzuna_provider.configured():raise HTTPException(404,'Match report not found.')
        if previous.input_hash!=fp:raise HTTPException(409,'This request ID was already used for different input.')
        return data(previous)
    job=resolve_job(payload.job_key,db)
    # Strip off generated suggestions and skill gaps: do not treat recommendations as facts.
    evidence={'strengths':resume.report.get('strengths',[]),
              'quoted_before_bullets':[x.get('before','') for x in resume.report.get('bullet_improvements',[]) if isinstance(x,dict)]}
    report=provider_call(user_id,gemini.job_match,evidence,text,job)
    row=JobMatchReport(user_id=user_id,resume_report_id=resume.id,request_id=payload.request_id,input_hash=fp,job_key=job['key'],job=job,report=report,model_name=get_settings().gemini_model)
    db.add(row);db.commit();db.refresh(row);return data(row)

@router.get('/detail/{job_key}')
def detail(job_key:str,user_id:UUID=Depends(current_user),db:Session=Depends(get_db)):
    return resolve_job(job_key,db)

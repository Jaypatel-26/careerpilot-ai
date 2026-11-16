from collections import defaultdict, deque
from datetime import datetime
import hashlib
from threading import Lock
from time import monotonic
from uuid import UUID
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from app.api.ai_interviews import provider_call
from app.core.config import get_settings
from app.core.security import current_user
from app.db.session import get_db
from app.models import User, ResumeReport
from app.schemas.resume import ResumeRequest, ResumeRead
from app.services import gemini
from app.services.resume_extract import extract_resume, MAX_BYTES

router=APIRouter(prefix='/resumes',tags=['Resume analysis'])
_upload_lock=Lock()
_uploads: dict[str,deque[float]]=defaultdict(deque)

def limit_upload(user_id:UUID):
    now=monotonic();key=str(user_id)
    with _upload_lock:
        for k in list(_uploads):
            if not _uploads[k] or _uploads[k][-1]<=now-3600: del _uploads[k]
        if key not in _uploads and len(_uploads)>=10000:
            raise HTTPException(429,'Too many uploads. Please try again later.',headers={'Retry-After':'60'})
        q=_uploads[key]
        while q and q[0]<=now-3600:q.popleft()
        if len(q)>=20: raise HTTPException(429,'Upload limit reached. Please try again later.',headers={'Retry-After':'3600'})
        q.append(now)

@router.post('/extract')
async def extract(file: UploadFile=File(...), user_id: UUID=Depends(current_user)):
    limit_upload(user_id)
    try:
        raw=await file.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES: raise HTTPException(413,'File must be no larger than 5 MB.')
        return await run_in_threadpool(extract_resume,raw,file.filename or '')
    finally:
        await file.close()

def owned(db:Session, user_id:UUID, report_id:UUID):
    row=db.scalar(select(ResumeReport).where(ResumeReport.id==report_id,ResumeReport.user_id==user_id))
    if not row: raise HTTPException(404,'Resume report not found.')
    return row

def response(row:ResumeReport): return {'id':row.id,'created_at':row.created_at,'report':row.report}

@router.post('/analyze',response_model=ResumeRead)
def analyze(payload:ResumeRequest,user_id:UUID=Depends(current_user),db:Session=Depends(get_db)):
    job=payload.job_description.strip();resume=payload.resume_text
    fingerprint=hashlib.sha256((str(len(resume))+':'+resume+job).encode('utf-8')).hexdigest()
    # User row lock serializes this account's analyses across PostgreSQL workers.
    db.scalar(select(User).where(User.id==user_id).with_for_update())
    previous=db.scalar(select(ResumeReport).where(ResumeReport.user_id==user_id,ResumeReport.request_id==payload.request_id))
    if previous:
        if previous.input_hash!=fingerprint: raise HTTPException(409,'This request ID was already used for different input.')
        return response(previous)
    report=provider_call(user_id,gemini.resume_analysis,resume,job)
    row=ResumeReport(user_id=user_id,request_id=payload.request_id,input_hash=fingerprint,report=report,model_name=get_settings().gemini_model)
    db.add(row);db.commit();db.refresh(row)
    return response(row)

@router.get('',response_model=list[ResumeRead])
def history(limit:int=Query(30,ge=1,le=100),offset:int=Query(0,ge=0),user_id:UUID=Depends(current_user),db:Session=Depends(get_db)):
    return [response(x) for x in db.scalars(select(ResumeReport).where(ResumeReport.user_id==user_id).order_by(ResumeReport.created_at.desc(),ResumeReport.id.desc()).offset(offset).limit(limit))]

@router.get('/{report_id}',response_model=ResumeRead)
def get_report(report_id:UUID,user_id:UUID=Depends(current_user),db:Session=Depends(get_db)):
    return response(owned(db,user_id,report_id))

@router.delete('/{report_id}',status_code=204)
def delete_report(report_id:UUID,user_id:UUID=Depends(current_user),db:Session=Depends(get_db)):
    db.delete(owned(db,user_id,report_id));db.commit()

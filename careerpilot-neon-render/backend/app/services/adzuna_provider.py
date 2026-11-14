"""Optional Adzuna India adapter. Never log credential-bearing provider URLs."""
from collections import defaultdict,deque
from datetime import datetime,timedelta,timezone
import logging
import hashlib
import re
from threading import Lock
from time import monotonic
from uuid import UUID
import httpx
from fastapi import HTTPException
from sqlalchemy import delete,select
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.models import JobSourceCache
from app.services.job_provider import TERMS,_mode,_experience,date_string,plain,safe_url

# Adzuna sends credentials in query parameters. HTTPX INFO logging contains the URL.
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
_lock=Lock();_calls:dict[str,deque[float]]=defaultdict(deque)
_search_lock=Lock();_search_cache:dict[tuple,tuple[float,dict]]={}
MAX_RESPONSE=3*1024*1024

def configured():
    s=get_settings();return bool(s.adzuna_app_id.strip() and s.adzuna_app_key.strip())

def _limit(user_id:UUID):
    now=monotonic();key=str(user_id)
    with _lock:
        for k in list(_calls):
            if not _calls[k] or _calls[k][-1]<=now-3600:del _calls[k]
        if key not in _calls and len(_calls)>=10000:raise HTTPException(429,'Job search is busy. Try again later.')
        q=_calls[key]
        while q and q[0]<=now-3600:q.popleft()
        if len(q)>=30:raise HTTPException(429,'Adzuna search limit reached. Try again later.',headers={'Retry-After':'3600'})
        q.append(now)

def _fetch(page,title,location,limit):
    s=get_settings();params={'app_id':s.adzuna_app_id,'app_key':s.adzuna_app_key,'results_per_page':limit,'content-type':'application/json'}
    if title.strip():params['what']=title.strip()
    if location.strip() and location.strip().casefold()!='india':params['where']=location.strip()
    url=f'https://api.adzuna.com/v1/api/jobs/in/search/{page}'
    try:
        with httpx.Client(timeout=15,follow_redirects=False,headers={'Accept':'application/json','User-Agent':'CareerPilotAI/1.0'}) as client:
            with client.stream('GET',url,params=params) as response:
                if response.status_code==429:raise HTTPException(429,'Adzuna quota reached. Please try again later.',headers={'Retry-After':'60'})
                response.raise_for_status();body=bytearray()
                for part in response.iter_bytes():
                    body.extend(part)
                    if len(body)>MAX_RESPONSE:raise ValueError('response too large')
        import json
        data=json.loads(body)
        if not isinstance(data,dict) or not isinstance(data.get('results'),list):raise ValueError('invalid response')
        return data
    except HTTPException:raise
    except (httpx.HTTPError,ValueError,TypeError,KeyError):
        raise HTTPException(503,'Adzuna is unavailable or not configured correctly. Please retry later.') from None

def cached_fetch(page,title,location,limit):
    settings=get_settings()
    credential_fingerprint=hashlib.sha256((settings.adzuna_app_id+"\0"+settings.adzuna_app_key).encode()).digest()
    key=(credential_fingerprint,page,title,location,limit)
    now=monotonic()
    with _search_lock:
        found=_search_cache.get(key)
        if found and now-found[0]<300:return found[1]
        data=_fetch(page,title,location,limit)
        for expired_key in [k for k,v in _search_cache.items() if now-v[0]>=300]:_search_cache.pop(expired_key,None)
        if len(_search_cache)>=16:_search_cache.pop(next(iter(_search_cache)))
        _search_cache[key]=(now,data)
        return data

def normalize(raw):
    if not isinstance(raw,dict):return None
    ident=str(raw.get('id') or '');title=str(raw.get('title') or '').strip()[:300]
    if not re.fullmatch(r'[0-9]{1,20}',ident) or not title:return None
    company=raw.get('company');company=str(company.get('display_name') or '').strip()[:200] if isinstance(company,dict) else ''
    loc=raw.get('location');location=str(loc.get('display_name') or '').strip()[:300] if isinstance(loc,dict) else ''
    description=plain(raw.get('description'));url=safe_url(raw.get('redirect_url'))
    mentioned=[t for t in TERMS if re.search(r'(?<!\w)'+re.escape(t)+r'(?!\w)',title+' '+description,re.I)]
    # Display only explicitly non-predicted salary; currency/period are not assumed.
    salary=None
    if raw.get('salary_is_predicted') in (0,'0',False):
        low,high=raw.get('salary_min'),raw.get('salary_max')
        if isinstance(low,(int,float)) and not isinstance(low,bool) and isinstance(high,(int,float)) and not isinstance(high,bool) and 0<=low<=high<=10**12:
            salary=f'Provider-reported range: {low:,.0f} – {high:,.0f} (currency/period not specified)'
    return {'key':f'adzuna~{ident}','title':title,'company':company or 'Not specified','location':location or 'Not specified',
      'description':description,'workplace':_mode(title,location),'experience':_experience(title),'skills_mentioned':mentioned,
      'salary':salary,'posted_at':date_string(raw.get('created')),'updated_at':None,'apply_url':url,'source':'Adzuna','source_board':'india'}

def search(db:Session,user_id:UUID,title:str,company:str,location:str,workplace:str,experience:str,skills:str,offset:int,limit:int):
    if not configured():raise HTTPException(503,'Adzuna is not configured yet. Ask the administrator to set up the job API.')
    if offset%limit!=0:raise HTTPException(422,'Invalid Adzuna pagination.')
    _limit(user_id)
    data=cached_fetch(offset//limit+1,title,location,limit)
    jobs=[j for r in data['results'][:limit] if (j:=normalize(r))]
    # Public provider data only. Cache is shared across app workers; stale entries are pruned on search.
    expiry=datetime.now(timezone.utc)+timedelta(minutes=30)
    db.execute(delete(JobSourceCache).where(JobSourceCache.expires_at<datetime.now(timezone.utc)))
    dialect=db.get_bind().dialect.name
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    for j in jobs:
        values={'job_key':j['key'],'job':j,'expires_at':expiry}
        if dialect in ('postgresql','sqlite'):
            ins=(pg_insert if dialect=='postgresql' else sqlite_insert)(JobSourceCache).values(**values)
            db.execute(ins.on_conflict_do_update(index_elements=['job_key'],set_={'job':ins.excluded.job,'expires_at':ins.excluded.expires_at}))
        else:db.merge(JobSourceCache(**values))
    db.commit()
    terms=[x.strip() for x in skills.split(',') if x.strip()][:10]
    filtered=[j for j in jobs if company.casefold().strip() in j['company'].casefold()
      and (not workplace or j['workplace']==workplace) and (not experience or j['experience']==experience)
      and all(re.search(r'(?<!\w)'+re.escape(t)+r'(?!\w)',j['title']+' '+j['description'],re.I) for t in terms)]
    try:count=max(0,min(int(data.get('count',0)),1000000))
    except (TypeError,ValueError,OverflowError):count=0
    return {'items':filtered,'total':count,'offset':offset,'limit':limit,'source':'Adzuna',
      'warnings':['Adzuna results are limited to India; company, skills, workplace and experience filters apply only to this returned page. Descriptions are excerpts. Browse later pages for more results.']}

def get_job(db:Session,key:str):
    if not re.fullmatch(r'adzuna~[0-9]{1,20}',key):raise HTTPException(404,'Job not found.')
    if not configured():raise HTTPException(503,'Adzuna is not configured.')
    row=db.scalar(select(JobSourceCache).where(JobSourceCache.job_key==key,JobSourceCache.expires_at>datetime.now(timezone.utc)))
    if not row:raise HTTPException(410,'This job snapshot expired. Search Adzuna again to refresh it.')
    return row.job

"""Public Greenhouse job board adapter: configured boards only, bounded reads, no user-supplied URLs."""
from datetime import datetime
from html import unescape
from html.parser import HTMLParser
from threading import Lock
from time import monotonic
from urllib.parse import urlsplit
import re
import ipaddress
import httpx
from fastapi import HTTPException
from app.core.config import get_settings

_token_re=re.compile(r'^[a-z0-9_-]{1,60}$')
_key_re=re.compile(r'^([a-z0-9_-]{1,60})~([0-9]{1,20})$')
_lock=Lock()
_cache:dict[str,tuple[float,list[dict]]]={}
_failure_until:dict[str,float]={}
MAX_BYTES=12*1024*1024
TERMS=['React','JavaScript','TypeScript','Python','Java','SQL','AWS','Azure','Docker','Kubernetes','Node.js','HTML','CSS','Git','Go','Rust','C++','C#','Figma','Linux']

class TextExtractor(HTMLParser):
    def __init__(self):super().__init__(convert_charrefs=True);self.parts=[];self.hidden=0
    def handle_starttag(self,tag,attrs):
        if tag.lower() in ('script','style'):self.hidden+=1
        if tag.lower() in ('p','li','br','h1','h2','h3','h4','div'):self.parts.append('\n')
    def handle_endtag(self,tag):
        if tag.lower() in ('script','style') and self.hidden:self.hidden-=1
        if tag.lower() in ('p','li','h1','h2','h3','h4','div'):self.parts.append('\n')
    def handle_data(self,data):
        if not self.hidden:self.parts.append(data)

def plain(value):
    p=TextExtractor();p.feed(unescape(str(value or '')));return re.sub(r'\n\s*\n+', '\n\n', ''.join(p.parts)).strip()[:30000]

def safe_url(value):
    if not isinstance(value,str) or len(value)>2048:return None
    try:
        u=urlsplit(value)
        host=u.hostname
        if u.scheme!='https' or not host or u.username or u.password or any(ord(c)<32 for c in value):return None
        if host.lower() in ('localhost',) or host.lower().endswith(('.localhost','.local','.internal')):return None
        try:
            if not ipaddress.ip_address(host).is_global:return None
        except ValueError:pass
        return value
    except ValueError:return None

def configured():
    tokens=[x.strip().lower() for x in get_settings().greenhouse_board_tokens.split(',') if x.strip()]
    if len(tokens)>5 or len(set(tokens))!=len(tokens) or any(not _token_re.fullmatch(t) or t=='adzuna' for t in tokens):
        raise HTTPException(503,'Job source configuration is invalid. Contact the administrator.')
    return tokens

def _json(url,params=None):
    with httpx.Client(timeout=15,follow_redirects=False,headers={'User-Agent':'CareerPilotAI/1.0 (job search)'}) as c:
        with c.stream('GET',url,params=params) as r:
            r.raise_for_status();buf=bytearray()
            for block in r.iter_bytes():
                buf.extend(block)
                if len(buf)>MAX_BYTES:raise ValueError('Feed is too large')
    import json
    return json.loads(buf)

def _mode(title,location):
    text=f'{title} {location}'.casefold()
    if re.search(r'\bhybrid\b',text):return 'hybrid'
    if re.search(r'\bremote\b',text):return 'remote'
    if re.search(r'\bon[ -]?site\b|\bin[ -]?office\b',text):return 'onsite'
    return 'unknown'

def _experience(title):
    t=title.casefold()
    if re.search(r'\bintern(ship)?\b',t):return 'internship'
    if re.search(r'\b(junior|entry[ -]level|graduate|new grad)\b',t):return 'entry'
    if re.search(r'\b(mid[ -]level|intermediate)\b',t):return 'mid'
    if re.search(r'\b(senior|sr\.?|staff|principal|lead)\b',t):return 'senior'
    return 'unknown'

def date_string(value):
    if not isinstance(value,str) or len(value)>60:return None
    try:datetime.fromisoformat(value.replace('Z','+00:00'))
    except ValueError:return None
    return value

def salary_ranges(items):
    # Only show provider-published structured ranges; never infer currency/period.
    if not isinstance(items,list):return None
    out=[]
    for r in items[:5]:
        if not isinstance(r,dict):continue
        low,high=r.get('min_cents'),r.get('max_cents')
        currency=str(r.get('currency_type') or '').strip()[:12]
        if isinstance(low,bool) or isinstance(high,bool) or not isinstance(low,int) or not isinstance(high,int) or low<0 or high<low or high>10**15 or not currency:continue
        title=plain(r.get('title'))[:120] or 'Published pay range (period not specified)'
        def money(cents):return f'{cents/100:,.2f}'.removesuffix('.00')
        out.append(f'{title}: {currency} {money(low)} – {money(high)}')
    return '; '.join(out) if out else None

def normalize(token,company,j):
    id=j.get('id');title=str(j.get('title') or '').strip()[:300]
    raw_location=j.get('location');location=str(raw_location.get('name') or '').strip()[:300] if isinstance(raw_location,dict) else ''
    if not str(id).isdigit() or not title:return None
    description=plain(j.get('content'));url=safe_url(j.get('absolute_url'))
    skills=[term for term in TERMS if re.search(r'(?<![\w])'+re.escape(term)+r'(?![\w])',title+' '+description,re.I)]
    return {'key':f'{token}~{id}','title':title,'company':company,'location':location or 'Not specified',
       'description':description,'workplace':_mode(title,location),'experience':_experience(title),'skills_mentioned':skills,
       'salary':salary_ranges(j.get('pay_input_ranges')),'posted_at':date_string(j.get('first_published')),'updated_at':date_string(j.get('updated_at')),'apply_url':url,'source':'Greenhouse',
       'source_board':token}

def _board(token):
    now=monotonic();cached=_cache.get(token)
    if cached and now-cached[0]<max(300,min(get_settings().jobs_cache_seconds,86400)):return cached[1]
    with _lock:
        now=monotonic();cached=_cache.get(token)
        if cached and now-cached[0]<max(300,min(get_settings().jobs_cache_seconds,86400)):return cached[1]
        if _failure_until.get(token,0)>now:raise ValueError('Provider temporarily unavailable')
        base=f'https://boards-api.greenhouse.io/v1/boards/{token}'
        try:
            meta=_json(base)
            if not isinstance(meta,dict):raise ValueError('Invalid board metadata')
            company=str(meta.get('name') or '').strip()[:200]
            feed=_json(base+'/jobs',{'content':'true','pay_transparency':'true'})
            if not isinstance(feed,dict):raise ValueError('Invalid board feed')
            items=feed.get('jobs')
            if not company or not isinstance(items,list):raise ValueError('Invalid provider response')
            if len(items)>3000:raise ValueError('Feed exceeds safety limit; configure a smaller board')
        except (httpx.HTTPError,ValueError,KeyError,TypeError,OverflowError):
            _failure_until[token]=now+60
            raise
        _failure_until.pop(token,None)
        result=[]
        for raw in items[:3000]:
            if isinstance(raw,dict):
                item=normalize(token,company,raw)
                if item:result.append(item)
        _cache[token]=(now,result)
        return result

def feed():
    tokens=configured()
    if not tokens:return [],['No job boards configured. An administrator must configure GREENHOUSE_BOARD_TOKENS.']
    items=[];failed=[]
    for token in tokens:
        try:items.extend(_board(token))
        except (httpx.HTTPError,ValueError,KeyError,TypeError,OverflowError):failed.append(token)
    if failed and not items:raise HTTPException(503,'The job source is temporarily unavailable. Please try again later.')
    warnings=['Some configured job boards are temporarily unavailable; results may be incomplete.'] if failed else []
    return items,warnings

def get_job(key):
    match=_key_re.fullmatch(key)
    if not match or match.group(1) not in configured():raise HTTPException(404,'Job not found.')
    try:items=_board(match.group(1))
    except (httpx.HTTPError,ValueError,KeyError,TypeError,OverflowError) as exc:raise HTTPException(503,'The job source is temporarily unavailable. Please try again later.') from exc
    result=next((x for x in items if x['key']==key),None)
    if not result:raise HTTPException(404,'This job is no longer available from the provider.')
    return result

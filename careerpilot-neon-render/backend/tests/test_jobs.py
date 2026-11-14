from uuid import uuid4
from app.api.ai_interviews import _calls
from app.services import job_provider,gemini
from app.schemas.job import JobMatchAnalysis
from test_foundation import client,signup,auth
from test_resume import TEXT,analysis

JOBS=[{'id':123,'title':'Junior React Developer','location':{'name':'Remote, India'},'content':'&lt;p&gt;Must know React, JavaScript and SQL.&lt;/p&gt;','absolute_url':'https://company.example/jobs/123','updated_at':'2026-11-01T00:00:00Z','first_published':'2026-10-28T00:00:00Z','pay_input_ranges':[{'min_cents':10000000,'max_cents':14000000,'currency_type':'USD','title':'Annual pay'}]},
      {'id':124,'title':'Senior Python Engineer','location':{'name':'Hybrid, Ahmedabad'},'content':'<p>Python and Docker required.</p>','absolute_url':'javascript:alert(1)','updated_at':'2026-10-01T00:00:00Z'}]
def job_ai():return {'match_score':71,'matching_skills':['React'],'missing_skills':['SQL'],'important_requirements':['JavaScript'],'requirements_not_evidenced':['SQL'],'improvements':['Verify skills'],'recommended_roles':['Frontend developer'],'evidence_limitations':['Resume report may be incomplete']}

def setup(monkeypatch):
    from app.core.config import get_settings
    monkeypatch.setenv('GREENHOUSE_BOARD_TOKENS','gitlab,figma');get_settings.cache_clear()
    _calls.clear();job_provider._cache.clear();job_provider._failure_until.clear()
    def fake_json(url,params=None):return {'jobs':JOBS} if url.endswith('/jobs') else {'name':'Example Employer'}
    monkeypatch.setattr(job_provider,'_json',fake_json)
    monkeypatch.setattr(gemini,'resume_analysis',lambda text,job:{**analysis(False),'job_match':None})
    monkeypatch.setattr(gemini,'job_match',lambda evidence,text,job:job_ai())

def test_search_details_filters_and_safe_links(client,monkeypatch):
    setup(monkeypatch);h=auth(signup(client));root='/api/v1/jobs'
    assert client.get(root+'/search').status_code==401
    r=client.get(root+'/search',headers=h);assert r.status_code==200 and r.json()['total']==4
    r=client.get(root+'/search',headers=h,params={'title':'react','company':'Example','location':'India','workplace':'remote','experience':'entry','skills':'React, SQL'})
    assert r.json()['total']==2 and r.json()['items'][0]['title']=='Junior React Developer'
    assert client.get(root+'/search',headers=h,params={'workplace':'onsite'}).json()['total']==0
    job=client.get(root+'/detail/gitlab~123',headers=h).json()
    assert job['description']=='Must know React, JavaScript and SQL.' and job['apply_url']=='https://company.example/jobs/123'
    assert job['posted_at']=='2026-10-28T00:00:00Z' and job['salary']=='Annual pay: USD 100,000 – 140,000'
    assert client.get(root+'/detail/gitlab~124',headers=h).json()['apply_url'] is None
    assert client.get(root+'/detail/invalid~123',headers=h).status_code==404
    assert client.get(root+'/search',headers=h,params={'workplace':'madeup'}).status_code==422
    assert job_provider.plain('<p>hello</p><script>alert(1)</script>')=='hello'
    assert job_provider.safe_url('https://user:password@evil.example') is None
    assert job_provider.safe_url('https://127.0.0.1/admin') is None

def test_saved_jobs_and_matching_are_account_owned(client,monkeypatch):
    setup(monkeypatch);a,b=auth(signup(client)),auth(signup(client,'two@example.com'));root='/api/v1/jobs'
    r=client.post('/api/v1/resumes/analyze',headers=a,json={'request_id':str(uuid4()),'resume_text':TEXT});assert r.status_code==200
    rid=r.json()['id'];save=client.post(root+'/saved',headers=a,json={'job_key':'gitlab~123'});assert save.status_code==200
    sid=save.json()['id'];assert client.post(root+'/saved',headers=a,json={'job_key':'gitlab~123'}).json()['id']==sid
    assert client.get(root+'/saved',headers=b).json()==[] and client.delete(root+'/saved/'+sid,headers=b).status_code==404
    body={'request_id':str(uuid4()),'resume_report_id':rid,'job_key':'gitlab~123','verified_resume_text':TEXT}
    assert client.post(root+'/match',headers=b,json=body).status_code==404
    m=client.post(root+'/match',headers=a,json=body);assert m.status_code==200,m.text
    mid=m.json()['id'];assert m.json()['report']['match_score']==71
    assert client.post(root+'/match',headers=a,json=body).json()['id']==mid
    assert client.post(root+'/match',headers=a,json={**body,'verified_resume_text':TEXT+' change'}).status_code==409
    assert client.get(root+'/matches',headers=b).json()==[]
    assert client.get(root+'/matches/'+mid,headers=b).status_code==404
    assert client.delete(root+'/matches/'+mid,headers=b).status_code==404
    assert client.get(root+'/matches/'+mid,headers=a).json()['report']['matching_skills']==['React']
    # Deleting original report preserves match while removing foreign key.
    assert client.delete('/api/v1/resumes/'+rid,headers=a).status_code==204
    assert client.get(root+'/matches/'+mid,headers=a).json()['resume_report_id'] is None
    assert client.delete(root+'/matches/'+mid,headers=a).status_code==204
    assert client.delete(root+'/saved/'+sid,headers=a).status_code==204

def test_provider_configuration_failure_and_gemini_prompt(client,monkeypatch):
    setup(monkeypatch);h=auth(signup(client));root='/api/v1/jobs'
    monkeypatch.setenv('GREENHOUSE_BOARD_TOKENS','')
    from app.core.config import get_settings
    get_settings.cache_clear()
    r=client.get(root+'/search',headers=h);assert r.status_code==200 and 'No job boards configured' in r.json()['warnings'][0]
    monkeypatch.setenv('GREENHOUSE_BOARD_TOKENS','https://evil')
    get_settings.cache_clear();assert client.get(root+'/search',headers=h).status_code==503
    monkeypatch.setenv('GREENHOUSE_BOARD_TOKENS','gitlab');get_settings.cache_clear()
    monkeypatch.undo() # restore real job_match and provider
    calls=[]
    def generate(prompt,schema,**kwargs):calls.append(prompt);return JobMatchAnalysis.model_validate(job_ai())
    monkeypatch.setattr(gemini,'_generate',generate)
    from importlib import reload
    # setup patched job_match as well, and undo restored original.
    out=gemini.job_match({'strengths':['Clear']},'',{'title':'Developer','company':'Company','location':'Remote','description':'React'})
    assert out['match_score']==71 and 'untrusted DATA' in calls[0] and 'Never claim' in calls[0]
    get_settings.cache_clear()

def test_provider_failure_quota_and_untrusted_report_evidence(client,monkeypatch):
    setup(monkeypatch);h=auth(signup(client));root='/api/v1/jobs'
    r=client.post('/api/v1/resumes/analyze',headers=h,json={'request_id':str(uuid4()),'resume_text':TEXT});rid=r.json()['id']
    calls=[]
    def provider(evidence,text,job):
        calls.append((evidence,text,job))
        raise gemini.AIServiceError(429,'AI quota or rate limit reached.',60)
    monkeypatch.setattr(gemini,'job_match',provider)
    payload={'job_key':'gitlab~123','request_id':str(uuid4()),'resume_report_id':rid,'verified_resume_text':''}
    res=client.post(root+'/match',headers=h,json=payload)
    assert res.status_code==429 and res.headers['retry-after']=='60'
    assert client.get(root+'/matches',headers=h).json()==[]
    assert 'missing_skills' not in calls[0][0] and 'strengths' in calls[0][0] and calls[0][1]==''
    assert client.post(root+'/match',headers=h,json={**payload,'verified_resume_text':'short'}).status_code==422
    job_provider._cache.clear();job_provider._failure_until.clear()
    import httpx
    monkeypatch.setattr(job_provider,'_json',lambda *args,**kwargs:(_ for _ in ()).throw(httpx.ConnectError('offline')))
    result=client.get(root+'/search',headers=h);assert result.status_code==503
    assert 'offline' not in result.text

def test_jobs_cors_preflight_and_owner_auth(client):
    o='http://localhost:5173'
    r=client.options('/api/v1/jobs/match',headers={'Origin':o,'Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'authorization,content-type'})
    assert r.status_code==200 and r.headers['access-control-allow-origin']==o
    assert client.get('/api/v1/jobs/saved').status_code==401
    assert client.get('/api/v1/jobs/matches').status_code==401

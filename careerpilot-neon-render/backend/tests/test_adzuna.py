from datetime import datetime,timedelta,timezone
from uuid import uuid4
from sqlalchemy import update
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.models import JobSourceCache
from app.services import adzuna_provider,gemini
from test_foundation import client,signup,auth
from test_resume import TEXT,analysis
from test_jobs import job_ai

FAKE={'count':42,'results':[{'id':'998877','title':'React Developer','company':{'display_name':'Mock Employer'},'location':{'display_name':'Ahmedabad, India'},'description':'React and JavaScript required.','created':'2026-11-01T00:00:00Z','redirect_url':'https://www.adzuna.in/jobs/123','salary_min':200000,'salary_max':300000,'salary_is_predicted':1}]}

def config(monkeypatch):
    monkeypatch.setenv('ADZUNA_APP_ID','test-id');monkeypatch.setenv('ADZUNA_APP_KEY','test-secret-not-real');get_settings.cache_clear();adzuna_provider._calls.clear();adzuna_provider._search_cache.clear()
    monkeypatch.setattr(adzuna_provider,'_fetch',lambda *a:FAKE)
    monkeypatch.setattr(gemini,'resume_analysis',lambda text,job:{**analysis(False),'job_match':None})
    monkeypatch.setattr(gemini,'job_match',lambda *a:job_ai())

def test_adzuna_search_cache_match_save_and_expiry(client,monkeypatch):
    config(monkeypatch);h=auth(signup(client));h2=auth(signup(client,'other@example.com'))
    assert client.get('/api/v1/jobs/search?source=adzuna').status_code==401
    r=client.get('/api/v1/jobs/search',headers=h,params={'source':'adzuna','title':'React','location':'Ahmedabad'});assert r.status_code==200,r.text
    body=r.json();job=body['items'][0];assert body['source']=='Adzuna' and body['total']==42 and job['key']=='adzuna~998877'
    assert job['apply_url']=='https://www.adzuna.in/jobs/123' and job['salary'] is None
    assert client.get('/api/v1/jobs/detail/adzuna~998877',headers=h).json()['description']=='React and JavaScript required.'
    assert client.get('/api/v1/jobs/search',headers=h,params={'source':'adzuna','company':'wrong'}).json()['items']==[]
    assert client.post('/api/v1/jobs/saved',headers=h,json={'job_key':job['key']}).status_code==200
    assert client.get('/api/v1/jobs/saved',headers=h2).json()==[]
    resume=client.post('/api/v1/resumes/analyze',headers=h,json={'request_id':str(uuid4()),'resume_text':TEXT}).json()
    matched=client.post('/api/v1/jobs/match',headers=h,json={'request_id':str(uuid4()),'resume_report_id':resume['id'],'job_key':job['key']});assert matched.status_code==200,matched.text
    assert matched.json()['report']['match_score']==71
    assert client.get('/api/v1/jobs/matches/'+matched.json()['id'],headers=h2).status_code==404
    with Session(client.engine) as db:
        db.execute(update(JobSourceCache).values(expires_at=datetime.now(timezone.utc)-timedelta(minutes=1)));db.commit()
    assert client.get('/api/v1/jobs/detail/adzuna~998877',headers=h).status_code==410
    # A saved external application link remains visible; fresh details require a new search.
    assert client.get('/api/v1/jobs/saved',headers=h).json()[0]['job']['apply_url'].startswith('https://')
    monkeypatch.setenv('ADZUNA_APP_ID','');get_settings.cache_clear()
    assert client.get('/api/v1/jobs/saved',headers=h).json()==[]
    assert client.get('/api/v1/jobs/matches',headers=h).json()==[]
    assert client.get('/api/v1/jobs/matches/'+matched.json()['id'],headers=h).status_code==404

def test_adzuna_configuration_and_url_safety(client,monkeypatch):
    monkeypatch.setenv('ADZUNA_APP_ID','');monkeypatch.setenv('ADZUNA_APP_KEY','');get_settings.cache_clear()
    h=auth(signup(client));r=client.get('/api/v1/jobs/search?source=adzuna',headers=h);assert r.status_code==503 and 'not configured' in r.text
    assert adzuna_provider.normalize({**FAKE['results'][0],'redirect_url':'javascript:alert(1)'})['apply_url'] is None
    assert adzuna_provider.normalize({**FAKE['results'][0],'redirect_url':'http://example.com'})['apply_url'] is None
    assert adzuna_provider.normalize({**FAKE['results'][0],'redirect_url':'https://127.0.0.1/admin'})['apply_url'] is None
    assert adzuna_provider.normalize({**FAKE['results'][0],'id':'abc'}) is None

def test_combined_results_and_provider_failure_are_truthful(client,monkeypatch):
    config(monkeypatch);h=auth(signup(client))
    from app.services import job_provider
    j=job_provider.normalize('gitlab','Public Board',{'id':42,'title':'React Developer','location':{'name':'Ahmedabad'},'content':'React','absolute_url':'https://example.com/42'})
    monkeypatch.setattr(job_provider,'feed',lambda:([j],[]))
    r=client.get('/api/v1/jobs/search?source=all&title=React',headers=h);assert r.status_code==200,r.text
    assert {x['source'] for x in r.json()['items']}=={'Greenhouse','Adzuna'}
    assert r.json()['source_counts']=={'Greenhouse':1,'Adzuna':42}
    monkeypatch.setenv('ADZUNA_APP_ID','');get_settings.cache_clear()
    r=client.get('/api/v1/jobs/search?source=all&title=React',headers=h);assert r.status_code==200
    assert [x['source'] for x in r.json()['items']]==['Greenhouse'] and any('not configured' in w for w in r.json()['warnings'])
    x={**FAKE['results'][0],'salary_is_predicted':0};assert 'Provider-reported range' in adzuna_provider.normalize(x)['salary']

def test_admin_purge_deletes_only_adzuna(client,monkeypatch):
    config(monkeypatch);h=auth(signup(client))
    from scripts import purge_adzuna
    from app.models import SavedJob,JobMatchReport,JobSourceCache
    from sqlalchemy import select,func
    r=client.get('/api/v1/jobs/search?source=adzuna',headers=h);key=r.json()['items'][0]['key']
    assert client.post('/api/v1/jobs/saved',headers=h,json={'job_key':key}).status_code==200
    resume=client.post('/api/v1/resumes/analyze',headers=h,json={'request_id':str(uuid4()),'resume_text':TEXT}).json()
    m=client.post('/api/v1/jobs/match',headers=h,json={'request_id':str(uuid4()),'resume_report_id':resume['id'],'job_key':key});assert m.status_code==200
    monkeypatch.setattr(purge_adzuna,'get_engine',lambda:client.engine)
    monkeypatch.setattr('sys.argv',['purge_adzuna']);assert purge_adzuna.main()==2
    with Session(client.engine) as db:assert db.scalar(select(func.count()).select_from(SavedJob))==1
    monkeypatch.setattr('sys.argv',['purge_adzuna','--confirm-delete-all-adzuna']);assert purge_adzuna.main()==0
    with Session(client.engine) as db:
        for table in (SavedJob,JobMatchReport,JobSourceCache):assert db.scalar(select(func.count()).select_from(table))==0

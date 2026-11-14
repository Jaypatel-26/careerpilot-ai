import io
from uuid import uuid4
import pytest
from docx import Document
from pypdf import PdfWriter
from reportlab.pdfgen import canvas
from app.api.resumes import _uploads
from app.api.ai_interviews import _calls
from app.schemas.resume import ResumeAnalysis, ResumeWithJob
from app.services import gemini
from test_foundation import client, signup, auth

TEXT='Jane Example is a developer who built accessible user interfaces with React and Python.'

def pdf_bytes(text=TEXT, pages=1):
    out=io.BytesIO();pdf=canvas.Canvas(out)
    for _ in range(pages):
        pdf.drawString(40,740,text);pdf.showPage()
    pdf.save();return out.getvalue()

def docx_bytes():
    doc=Document();doc.add_paragraph(TEXT);table=doc.add_table(rows=1,cols=1);table.cell(0,0).text='Education and project experience';out=io.BytesIO();doc.save(out);return out.getvalue()

def analysis(job=False):
    r={'overall_score':75,'ats_score':70,'strengths':['Clear'],'weaknesses':['Detail'],'missing_skills':['Testing'],'missing_sections':['Projects'],'grammar_suggestions':['Use consistent tense'],'project_improvements':['Explain approach'],'experience_suggestions':['Add context'],'education_skills_review':['Clarify education'],'formatting_suggestions':['Use headings'],'action_verbs':['Built'],'measurable_achievement_suggestions':['Add a verified metric'],'bullet_improvements':[{'before':'built accessible user interfaces','after':'Built accessible user interfaces','note':'Verify details'}]}
    if job:r['job_match']={'score':60,'matching_skills':['React'],'missing_skills':['SQL'],'matching_keywords':['React'],'missing_keywords':['SQL'],'requirements_not_covered':['SQL'],'targeted_suggestions':['Explain relevant work'],'project_suggestions':['Practice SQL']}
    return r

@pytest.fixture(autouse=True)
def limits():
    _uploads.clear();_calls.clear();yield;_uploads.clear();_calls.clear()

def test_extract_real_pdf_docx_and_invalid(client):
    h=auth(signup(client));url='/api/v1/resumes/extract'
    assert client.post(url,files={'file':('resume.pdf',pdf_bytes(),'application/pdf')}).status_code==401
    for name,raw in [('resume.pdf',pdf_bytes()),('resume.docx',docx_bytes())]:
        r=client.post(url,headers=h,files={'file':(name,raw,'application/octet-stream')})
        assert r.status_code==200,(name,r.text)
        assert 'accessible user interfaces' in r.json()['text']
        if name.endswith('.docx'):assert 'Education and project' in r.json()['text']
        assert r.headers['cache-control']=='no-store'
    for name,raw,status in [('bad.pdf',b'garbage',415),('bad.docx',b'PK\x03\x04garbage',422),('bad.txt',b'text',415),('empty.pdf',b'',422),('too-large.pdf',b'%PDF-'+b'x'*(5*1024*1024),413),('many.pdf',pdf_bytes(pages=13),422),('scan.pdf',pdf_bytes(''),422)]:
        r=client.post(url,headers=h,files={'file':(name,raw,'application/octet-stream')});assert r.status_code==status,(name,r.status_code,r.text)
    assert 'OCR' in r.text

def test_report_ownership_idempotency_and_validation(client,monkeypatch):
    a,b=auth(signup(client)),auth(signup(client,'other@example.com'))
    calls=[]
    def fake(text,job):calls.append((text,job));return {**analysis(bool(job)),**({} if job else {'job_match':None})}
    monkeypatch.setattr(gemini,'resume_analysis',fake)
    data={'request_id':str(uuid4()),'resume_text':TEXT,'job_description':'Looking for React and SQL'};url='/api/v1/resumes'
    assert client.post(url+'/analyze',json=data).status_code==401
    assert client.post(url+'/analyze',headers=a,json={**data,'resume_text':'short'}).status_code==422
    first=client.post(url+'/analyze',headers=a,json=data);assert first.status_code==200,first.text
    report=first.json();rid=report['id'];assert report['report']['job_match']['score']==60
    assert client.post(url+'/analyze',headers=a,json=data).json()['id']==rid
    assert len(calls)==1
    assert client.post(url+'/analyze',headers=a,json={**data,'resume_text':TEXT+' changed'}).status_code==409
    assert len(client.get(url,headers=a).json())==1 and client.get(url,headers=b).json()==[]
    assert client.get(url+'/'+rid,headers=b).status_code==404
    assert client.delete(url+'/'+rid,headers=b).status_code==404
    assert client.get(url+'/'+rid,headers=a).json()['report']['ats_score']==70
    assert client.delete(url+'/'+rid,headers=a).status_code==204
    assert client.get(url+'/'+rid,headers=a).status_code==404
    r=client.post(url+'/analyze',headers=b,json={**data,'request_id':str(uuid4()),'job_description':''});assert r.status_code==200 and r.json()['report']['job_match'] is None

def test_provider_prompt_schema_and_failure(client,monkeypatch):
    prompts=[]
    def fake(prompt,schema,**kwargs):
        prompts.append((prompt,schema,kwargs));return schema.model_validate(analysis(schema is ResumeWithJob))
    monkeypatch.setattr(gemini,'_generate',fake)
    assert gemini.resume_analysis(TEXT,'')['job_match'] is None
    assert gemini.resume_analysis(TEXT,'React')['job_match']['matching_skills']==['React']
    assert 'NEVER invent' in prompts[0][0] and 'untrusted DATA' in prompts[0][0]
    assert prompts[0][1] is ResumeAnalysis and prompts[1][1] is ResumeWithJob
    assert prompts[1][2]['schema_override']
    def fail(*args):raise gemini.AIServiceError(429,'AI quota or rate limit reached.',60)
    monkeypatch.setattr(gemini,'resume_analysis',fail)
    h=auth(signup(client));r=client.post('/api/v1/resumes/analyze',headers=h,json={'request_id':str(uuid4()),'resume_text':TEXT})
    assert r.status_code==429 and r.headers['retry-after']=='60'
    assert client.get('/api/v1/resumes',headers=h).json()==[]


def test_cross_origin_upload_preflight_and_size_errors(client):
    origin='http://localhost:5173'
    headers={'Origin':origin,'Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'authorization'}
    preflight=client.options('/api/v1/resumes/extract',headers=headers)
    assert preflight.status_code==200
    assert preflight.headers['access-control-allow-origin']==origin
    assert 'POST' in preflight.headers['access-control-allow-methods']
    h={**auth(signup(client)),'Origin':origin}
    upload=client.post('/api/v1/resumes/extract',headers=h,files={'file':('sample.pdf',pdf_bytes(),'application/pdf')})
    assert upload.status_code==200 and 'accessible user interfaces' in upload.json()['text']
    assert upload.headers['access-control-allow-origin']==origin
    oversized=client.post('/api/v1/resumes/extract',headers={**h,'Content-Length':str(6*1024*1024)},content=b'')
    assert oversized.status_code==413
    assert oversized.headers['access-control-allow-origin']==origin
    no_length=client.post('/api/v1/resumes/extract',headers=h,content=iter([b'chunked']))
    assert no_length.status_code==411
    assert no_length.headers['access-control-allow-origin']==origin

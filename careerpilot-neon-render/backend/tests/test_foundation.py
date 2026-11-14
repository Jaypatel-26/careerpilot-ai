import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.core.config import get_settings, Settings
from app.core.rate_limit import _attempts
from app.db.session import Base, get_db
from app.main import app as api
from app.models import User

SECRET = 'test-only-secret-at-least-32-characters-long'
PAYLOAD = {'target_role': 'Frontend Developer', 'interview_type': 'technical', 'difficulty': 'beginner', 'question_count': 3}

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv('JWT_SECRET_KEY', SECRET)
    get_settings.cache_clear()
    _attempts.clear()
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    @event.listens_for(engine, 'connect')
    def foreign_keys(conn, rec):
        conn.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine)
    def override_db():
        with Session(engine, expire_on_commit=False) as db:
            yield db
    api.dependency_overrides[get_db] = override_db
    with TestClient(api) as test_client:
        test_client.engine = engine
        yield test_client
    api.dependency_overrides.clear()
    engine.dispose()
    _attempts.clear()
    get_settings.cache_clear()


def signup(client, email='one@example.com', password='correct-horse-battery'):
    return client.post('/api/v1/auth/signup', json={'full_name':'Test User','email':email,'password':password})


def auth(result):
    return {'Authorization': 'Bearer ' + result.json()['access_token']}


def test_signup_password_hash_and_login(client):
    response = signup(client, 'ONE@example.com')
    assert response.status_code == 201
    assert response.json()['user']['email'] == 'one@example.com'
    assert 'password' not in str(response.json())
    with Session(client.engine) as db:
        user = db.scalar(select(User))
        assert user.password_hash.startswith('$argon2id$')
        assert 'correct-horse-battery' not in user.password_hash
    assert signup(client, 'one@example.com').status_code == 409
    assert client.post('/api/v1/auth/login', json={'email':'one@example.com','password':'wrong'}).status_code == 401
    assert client.post('/api/v1/auth/login', json={'email':'missing@example.com','password':'wrong'}).status_code == 401
    result = client.post('/api/v1/auth/login', json={'email':'ONE@example.com','password':'correct-horse-battery'})
    assert result.status_code == 200
    assert client.get('/api/v1/auth/me', headers=auth(result)).json()['email'] == 'one@example.com'
    assert signup(client, 'new@example.com', 'short').status_code == 422


def test_logout_revokes_stolen_token_and_does_not_revoke_other_session(client):
    first = signup(client)
    second = client.post('/api/v1/auth/login', json={'email':'one@example.com','password':'correct-horse-battery'})
    first_token, second_token = auth(first), auth(second)
    assert client.post('/api/v1/auth/logout', headers=first_token).status_code == 204
    assert client.get('/api/v1/auth/me', headers=first_token).status_code == 401
    assert client.get('/api/v1/interviews', headers=first_token).status_code == 401
    assert client.get('/api/v1/auth/me', headers=second_token).status_code == 200


def test_invalid_token_and_auth_required(client):
    assert client.get('/api/v1/health').json() == {'status':'ok'}
    assert client.get('/api/v1/interviews').status_code == 401
    bad = jwt.encode({'sub':str(uuid4()),'jti':str(uuid4()),'iss':'careerpilot-api','aud':'careerpilot-web','iat':datetime.now(timezone.utc),'exp':datetime.now(timezone.utc)+timedelta(minutes=5)}, 'bad-secret-with-more-than-32-characters', algorithm='HS256')
    assert client.get('/api/v1/auth/me', headers={'Authorization':'Bearer '+bad}).status_code == 401
    expired = jwt.encode({'sub':str(uuid4()),'jti':str(uuid4()),'iss':'careerpilot-api','aud':'careerpilot-web','iat':datetime.now(timezone.utc)-timedelta(minutes=3),'exp':datetime.now(timezone.utc)-timedelta(minutes=1)}, SECRET, algorithm='HS256')
    assert client.get('/api/v1/auth/me', headers={'Authorization':'Bearer '+expired}).status_code == 401
    unsigned = jwt.encode({'sub':str(uuid4())}, '', algorithm='none')
    assert client.get('/api/v1/auth/me', headers={'Authorization':'Bearer '+unsigned}).status_code == 401


def test_owner_isolation_and_input_validation(client):
    a, b = signup(client), signup(client, 'two@example.com')
    assert a.status_code == b.status_code == 201
    h1, h2 = auth(a), auth(b)
    created = client.post('/api/v1/interviews', headers=h1, json=PAYLOAD)
    assert created.status_code == 201
    session_id = created.json()['id']
    assert created.json()['status'] == 'draft'
    assert client.get('/api/v1/interviews', headers=h2).json() == []
    assert client.get(f'/api/v1/interviews/{session_id}', headers=h2).status_code == 404
    assert client.delete(f'/api/v1/interviews/{session_id}', headers=h2).status_code == 404
    assert client.get(f'/api/v1/interviews/{session_id}', headers=h1).status_code == 200
    assert client.delete(f'/api/v1/interviews/{session_id}', headers=h1).status_code == 204
    assert client.get(f'/api/v1/interviews/{session_id}', headers=h1).status_code == 404
    assert client.post('/api/v1/interviews', headers=h1, json={**PAYLOAD,'target_role':' '}).status_code == 422


def test_rate_limit(client):
    for _ in range(10):
        assert client.post('/api/v1/auth/login', json={'email':'missing@example.com','password':'wrong'}).status_code == 401
    assert client.post('/api/v1/auth/login', json={'email':'missing@example.com','password':'wrong'}).status_code == 429


def test_bad_signing_configuration(client, monkeypatch):
    monkeypatch.setenv('JWT_SECRET_KEY', 'short')
    get_settings.cache_clear()
    assert signup(client).status_code == 503
    with Session(client.engine) as db:
        assert db.scalar(select(User)) is None


def test_neon_url_adaptation():
    settings = Settings(database_url='postgresql://u:p@host/db?sslmode=require')
    assert settings.sqlalchemy_url == 'postgresql+psycopg://u:p@host/db?sslmode=require'


def test_migration_upgrade_downgrade(tmp_path):
    backend = Path(__file__).resolve().parents[1]
    env = dict(os.environ, DATABASE_URL=f"sqlite:///{tmp_path / 'migration.db'}")
    for direction in [('upgrade','head'),('downgrade','base'),('upgrade','head')]:
        subprocess.run([sys.executable,'-m','alembic',*direction], cwd=backend, env=env, check=True, capture_output=True)


def test_account_profiles_are_private_persistent_and_validated(client):
    a, b = signup(client), signup(client, 'two@example.com')
    h1, h2 = auth(a), auth(b)
    assert client.get('/api/v1/profile').status_code == 401
    assert client.patch('/api/v1/profile', json={}).status_code == 401
    initial = client.get('/api/v1/profile', headers=h1)
    assert initial.status_code == 200
    assert initial.headers['cache-control'] == 'no-store'
    assert initial.json()['full_name'] == 'Test User'
    assert initial.json()['skills'] == ''
    draft = client.post('/api/v1/interviews', headers=h1, json=PAYLOAD).json()
    fields = {'full_name':'  New Name  ', 'target_role':'Engineer', 'experience_level':'Experienced', 'skills':'Python, SQL', 'career_goals':'Build useful things'}
    saved = client.patch('/api/v1/profile', headers=h1, json=fields)
    assert saved.status_code == 200
    assert saved.json()['full_name'] == 'New Name'
    assert client.get('/api/v1/auth/me', headers=h1).json()['full_name'] == 'New Name'
    assert client.get('/api/v1/profile', headers=h2).json()['skills'] == ''
    assert client.patch('/api/v1/profile', headers=h2, json={**fields, 'id': a.json()['user']['id']}).status_code == 422
    for invalid in ({**fields, 'full_name':'   '}, {**fields, 'experience_level':'Expert'}, {**fields, 'skills':'x'*2001}, {**fields, 'email':'takeover@example.com'}):
        assert client.patch('/api/v1/profile', headers=h1, json=invalid).status_code == 422
    assert client.get('/api/v1/interviews/'+draft['id'], headers=h1).status_code == 200
    assert client.post('/api/v1/auth/logout', headers=h1).status_code == 204
    assert client.get('/api/v1/profile', headers=h1).status_code == 401
    again = client.post('/api/v1/auth/login', json={'email':'one@example.com', 'password':'correct-horse-battery'})
    assert client.get('/api/v1/profile', headers=auth(again)).json()['career_goals'] == 'Build useful things'


def test_profile_preflight_allows_patch(client):
    response = client.options('/api/v1/profile', headers={'Origin': 'http://localhost:5173', 'Access-Control-Request-Method': 'PATCH', 'Access-Control-Request-Headers': 'authorization,content-type'})
    assert response.status_code == 200
    assert 'PATCH' in response.headers['access-control-allow-methods']


def test_profile_migration_preserves_existing_accounts_and_drafts(tmp_path):
    from sqlalchemy import text
    backend = Path(__file__).resolve().parents[1]
    url = f"sqlite:///{tmp_path / 'preserve.db'}"
    env = dict(os.environ, DATABASE_URL=url)
    def migrate(*args):
        subprocess.run([sys.executable, '-m', 'alembic', *args], cwd=backend, env=env, check=True, capture_output=True)
    migrate('upgrade', '4d2e9a1b8c10')
    engine = create_engine(url)
    uid, sid = uuid4().hex, uuid4().hex
    with engine.begin() as db:
        db.execute(text("INSERT INTO users (id,email,full_name,password_hash,created_at) VALUES (:id,'old@example.com','Existing User','hash','2025-01-01')"), {'id':uid})
        # Insert a saved draft using the real pre-migration schema.
        columns = db.execute(text('PRAGMA table_info(interview_sessions)')).fetchall()
        # Use existing ORM defaults against the old schema for an accurately shaped row.
        print_columns = {c[1] for c in columns}
        assert {'id', 'user_id', 'target_role'} <= print_columns
        db.execute(text("INSERT INTO interview_sessions (id,user_id,target_role,interview_type,difficulty,question_count,status,created_at,updated_at) VALUES (:id,:uid,'Saved Role','technical','beginner',3,'draft','2025-01-01','2025-01-01')"), {'id':sid,'uid':uid})
    migrate('upgrade', 'head')
    with engine.connect() as db:
        assert db.execute(text('SELECT full_name, skills FROM users WHERE id=:id'), {'id':uid}).one() == ('Existing User', None)
        assert db.execute(text('SELECT target_role FROM interview_sessions WHERE id=:id'), {'id':sid}).scalar_one() == 'Saved Role'
    engine.dispose()

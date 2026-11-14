from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from app.api.interviews import router as interview_router
from app.api.auth import router as auth_router
from app.api.profile import router as profile_router
from app.api.ai_interviews import router as ai_interview_router
from app.api.resumes import router as resume_router
from app.api.jobs import router as job_router
from app.api.career import router as career_router
from app.core.config import get_settings
from app.db.session import get_engine

app = FastAPI(title="CareerPilot AI API", version="0.1.0")
app.include_router(interview_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(profile_router, prefix="/api/v1")
app.include_router(ai_interview_router, prefix="/api/v1")
app.include_router(resume_router, prefix="/api/v1")
app.include_router(job_router, prefix="/api/v1")
app.include_router(career_router, prefix="/api/v1")


@app.middleware("http")
async def prevent_auth_response_caching(request: Request, call_next):
    # Reject declared large uploads before multipart parsing; the endpoint also
    # bounds reads. An edge/body limit is still recommended for chunked uploads.
    if request.method == 'POST' and request.url.path == '/api/v1/resumes/extract':
        if 'content-length' not in request.headers:
            return JSONResponse(status_code=411, content={'detail':'Content-Length is required for file uploads.'}, headers={'Cache-Control':'no-store'})
        try:
            content_length = int(request.headers['content-length'])
        except ValueError:
            return JSONResponse(status_code=400, content={'detail':'Invalid content length.'})
        if content_length > 5*1024*1024 + 256*1024:
            return JSONResponse(status_code=413, content={'detail':'File must be no larger than 5 MB.'}, headers={'Cache-Control':'no-store'})
    response = await call_next(request)
    if request.url.path.startswith('/api/v1/auth/') or request.url.path == '/api/v1/profile' or request.url.path.startswith('/api/v1/interviews') or request.url.path.startswith('/api/v1/resumes') or request.url.path.startswith('/api/v1/jobs') or request.url.path.startswith('/api/v1/career'):
        response.headers['Cache-Control'] = 'no-store'
    return response


# Outermost CORS middleware handles browser OPTIONS preflight before upload
# validation and adds CORS headers even to early 411/413 responses.
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origins, allow_credentials=False,
                   allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"], allow_headers=["Authorization", "Content-Type"])


@app.get("/api/v1/health", tags=["health"])
def health():
    return {"status": "ok"}


@app.get("/api/v1/health/database", tags=["health"])
def database_health():
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database connection failed. Check server configuration.") from exc

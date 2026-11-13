from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from app.api.interviews import router as interview_router
from app.api.auth import router as auth_router
from app.core.config import get_settings
from app.db.session import get_engine

app = FastAPI(title="CareerPilot AI API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origins, allow_credentials=False,
                   allow_methods=["GET", "POST", "DELETE", "OPTIONS"], allow_headers=["Authorization", "Content-Type"])
app.include_router(interview_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")


@app.middleware("http")
async def prevent_auth_response_caching(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith('/api/v1/auth/'):
        response.headers['Cache-Control'] = 'no-store'
    return response


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

from functools import lru_cache
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


@lru_cache
def get_engine():
    url = get_settings().sqlalchemy_url
    if not url:
        raise HTTPException(status_code=503, detail="Database is not configured.")
    # A small pool avoids wasting Neon free-tier connections. pre_ping handles idle disconnects.
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=2)


def get_db():
    session_factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    with session_factory() as session:
        yield session

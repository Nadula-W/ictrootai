from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError, TimeoutError as DatabaseTimeout
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from fastapi import HTTPException
from .config import settings
from .config import validate_database_url

class Base(DeclarativeBase):
    pass

def build_engine(database_url, pool_size=5, max_overflow=5, pool_timeout=10, pool_recycle=1800):
    return create_engine(validate_database_url(database_url),pool_pre_ping=True,pool_size=pool_size,max_overflow=max_overflow,pool_timeout=pool_timeout,pool_recycle=pool_recycle,connect_args={'connect_timeout':10,'prepare_threshold':None},hide_parameters=True)

raw_url=settings.database_url.get_secret_value()
engine=build_engine(raw_url,settings.database_pool_size,settings.database_max_overflow,settings.database_pool_timeout,settings.database_pool_recycle) if raw_url else None
SessionLocal = sessionmaker(engine, expire_on_commit=False)

def get_db():
    if engine is None:
        raise HTTPException(503,'Supabase PostgreSQL is not configured. Set DATABASE_URL in backend/.env, then apply database migrations. No local database fallback is used.')
    with SessionLocal() as db:
        try:yield db
        except (OperationalError,DatabaseTimeout):
            db.rollback()
            raise HTTPException(503,'Cannot connect to the configured PostgreSQL database. Check the Supabase project, connection string and network.') from None

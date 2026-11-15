"""Read-only PostgreSQL connection check. Never prints credentials or raw DB errors."""
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from .database import engine

def main():
    if engine is None:
        print('PostgreSQL is not configured. Copy backend/.env.example to backend/.env and set DATABASE_URL from Supabase Connect. No SQLite fallback is available.')
        return 1
    try:
        with engine.connect() as connection:
            connection.execute(text('SELECT 1'))
            if connection.dialect.name!='postgresql':raise RuntimeError('PostgreSQL required')
            present=connection.scalar(text("SELECT to_regclass('public.alembic_version') IS NOT NULL"))
            revision=connection.scalar(text('SELECT version_num FROM public.alembic_version')) if present else None
        print('PostgreSQL connection: OK')
        print('Schema revision: '+str(revision or 'not migrated; run python -m alembic upgrade head'))
        return 0
    except (SQLAlchemyError,RuntimeError):
        print('PostgreSQL connection failed. Check the project status, DATABASE_URL, TLS settings and network. Credentials were not printed.')
        return 1

if __name__=='__main__':raise SystemExit(main())

from alembic import context
from app.database import Base, engine
from app import models

if context.is_offline_mode():
    from app.config import settings
    if not settings.database_url.get_secret_value():raise RuntimeError('Set DATABASE_URL in backend/.env before running migrations')
    context.configure(url=settings.database_url.get_secret_value(),target_metadata=Base.metadata,literal_binds=True)
    with context.begin_transaction():context.run_migrations()
else:
    if engine is None:raise RuntimeError('Set DATABASE_URL in backend/.env before running migrations')
    with engine.connect() as connection:
        context.configure(connection=connection,target_metadata=Base.metadata,compare_type=True)
        with context.begin_transaction():context.run_migrations()

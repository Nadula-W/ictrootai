from sqlalchemy import create_engine,event
import weakref
from sqlalchemy.exc import OperationalError, TimeoutError as DatabaseTimeout
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from fastapi import HTTPException
from .config import settings
from .config import validate_database_url
from .database_diagnostics import database_failure

class Base(DeclarativeBase):
    pass

def build_engine(database_url, pool_size=5, max_overflow=5, pool_timeout=10, pool_recycle=1800,transport='direct'):
    if transport not in ('direct','supabase_websocket'):raise ValueError('Unsupported PostgreSQL transport')
    normalized=validate_database_url(database_url)
    relay=None
    if transport=='supabase_websocket':
        from .postgres_websocket import PostgresWebSocketRelay
        relay=PostgresWebSocketRelay(normalized,max_connections=pool_size+max_overflow)
    database_engine=create_engine(normalized,pool_pre_ping=True,pool_size=pool_size,max_overflow=max_overflow,pool_timeout=pool_timeout,pool_recycle=pool_recycle,connect_args={'connect_timeout':10,'prepare_threshold':None},hide_parameters=True)
    if relay:
        @event.listens_for(database_engine,'do_connect')
        def connect_through_websocket(dialect,connection_record,args,params):
            # Keep the original remote host for PG TLS/SNI and verification.
            # Only the TCP address is redirected to the loopback byte relay.
            params['hostaddr']='127.0.0.1'
            params['port']=relay.start()
            params['gssencmode']='disable'
        @event.listens_for(database_engine,'engine_disposed')
        def stop_unused_listener(disposed_engine):
            # SQLAlchemy disposal leaves already checked-out connections alive.
            # Stop only new local accepts; a later do_connect restarts lazily.
            relay.stop_listener()
        weakref.finalize(database_engine,relay.close)
    return database_engine

raw_url=settings.database_url.get_secret_value()
engine=build_engine(raw_url,settings.database_pool_size,settings.database_max_overflow,settings.database_pool_timeout,settings.database_pool_recycle,settings.database_transport) if raw_url else None
SessionLocal = sessionmaker(engine, expire_on_commit=False)

def get_db():
    if engine is None:
        raise HTTPException(503,'Supabase PostgreSQL is not configured. Set DATABASE_URL in backend/.env, then apply database migrations. No local database fallback is used.')
    with SessionLocal() as db:
        try:yield db
        except (OperationalError,DatabaseTimeout) as error:
            db.rollback()
            code,message=database_failure(error)
            raise HTTPException(503,message,headers={'X-Database-Error':code}) from None

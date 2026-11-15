"""Configuration checks do not require a running database or real credentials."""
import os
from pathlib import Path
import subprocess
import sys
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.engine import make_url

from app.config import Settings, validate_database_url
from app import database


def configured_settings(**values):
    return Settings(_env_file=None,environment='development',secure_cookies=False,**values)


def test_no_implicit_application_database():
    settings=configured_settings(database_url='')
    assert settings.database_url.get_secret_value()==''


@pytest.mark.parametrize('driver',['postgres','postgresql','postgresql+psycopg'])
def test_postgres_urls_normalize_to_psycopg(driver):
    url=make_url(validate_database_url(f'{driver}://test:example@localhost:5432/ictroot'))
    assert url.drivername=='postgresql+psycopg'
    assert url.host=='localhost'
    assert url.database=='ictroot'


@pytest.mark.parametrize('value',[
    'sqlite:///./ictroot.db',
    'sqlite://',
    'mysql://test:example@localhost/ictroot',
    'postgresql://test:example@database.example/ictroot',
    'postgresql://test:example@database.example/ictroot?sslmode=disable',
    'postgresql://test:example@database.example/ictroot?sslmode=prefer',
])
def test_non_postgres_or_unencrypted_remote_database_is_rejected(value):
    with pytest.raises(ValueError):validate_database_url(value)


@pytest.mark.parametrize('mode',['require','verify-ca','verify-full'])
def test_remote_postgres_requires_encrypted_transport(mode):
    url=make_url(validate_database_url(f'postgresql://test:example@database.example:5432/ictroot?sslmode={mode}'))
    assert url.query['sslmode']==mode


def test_database_url_is_redacted_in_settings_repr():
    settings=configured_settings(database_url='postgresql://test:DO-NOT-LOG-THIS@localhost/ictroot')
    assert 'DO-NOT-LOG-THIS' not in repr(settings)
    assert 'DO-NOT-LOG-THIS' not in str(settings.database_url)


def test_invalid_settings_do_not_expose_url_credentials():
    with pytest.raises((ValidationError,ValueError)) as captured:
        configured_settings(database_url='mysql://test:DO-NOT-LOG-THIS@localhost/ictroot')
    assert 'DO-NOT-LOG-THIS' not in str(captured.value)


def test_unconfigured_request_returns_actionable_503(monkeypatch):
    monkeypatch.setattr(database,'engine',None)
    with pytest.raises(HTTPException) as captured:
        next(database.get_db())
    assert captured.value.status_code==503
    assert 'DATABASE_URL' in captured.value.detail


def test_engine_cannot_restore_sqlite_fallback():
    with pytest.raises(ValueError):database.build_engine('sqlite:///./ictroot.db')


def test_postgres_engine_can_be_built_without_connecting():
    engine=database.build_engine('postgresql://test:example@127.0.0.1:5432/ictroot',pool_size=3,max_overflow=2)
    try:
        assert engine.url.get_backend_name()=='postgresql'
        assert engine.url.get_driver_name()=='psycopg'
        assert engine.pool.size()==3
    finally:
        engine.dispose()


def test_database_configuration_wizard_can_recover_legacy_settings():
    environment=os.environ.copy()
    environment['DATABASE_URL']='sqlite:///./legacy.db'
    result=subprocess.run([sys.executable,'-c','import app.configure_database'],cwd=Path(__file__).resolve().parents[1],env=environment,capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stderr


def test_configuration_helper_adds_tls_to_remote_connection_string():
    from app.configure_database import prepare_connection_url
    url=make_url(prepare_connection_url('postgresql://test:example@database.example/ictroot'))
    assert url.drivername=='postgresql+psycopg'
    assert url.query['sslmode']=='require'


def test_configuration_helper_preserves_stronger_tls():
    from app.configure_database import prepare_connection_url
    url=make_url(prepare_connection_url('postgresql://test:example@database.example/ictroot?sslmode=verify-full'))
    assert url.query['sslmode']=='verify-full'


def test_configuration_helper_cannot_accept_explicit_insecure_remote_tls():
    from app.configure_database import prepare_connection_url
    with pytest.raises(ValueError):
        prepare_connection_url('postgresql://test:example@database.example/ictroot?sslmode=disable')

from types import SimpleNamespace
import pytest
from sqlalchemy.exc import OperationalError
from app.database_diagnostics import database_failure

@pytest.mark.parametrize('raw,state,code',[
    ('connection timeout expired',None,'database_timeout'),
    ('connection timed out',None,'database_timeout'),
    ('password authentication failed',None,'database_password_rejected'),
    ('authentication error','28P01','database_password_rejected'),
    ('Tenant or user not found',None,'database_destination_invalid'),
    ('could not translate host name',None,'database_dns_failure'),
    ('certificate verify failed',None,'database_tls_failure'),
    ('unknown failure',None,'database_unavailable'),
])
def test_driver_errors_return_only_safe_messages(raw,state,code):
    class DriverFailure(Exception):
        sqlstate=state
    private='PRIVATE-PASSWORD-DO-NOT-DISPLAY'
    error=OperationalError('SELECT 1',None,DriverFailure(raw+' '+private))
    category,message=database_failure(error)
    assert category==code
    assert private not in message

def test_timeout_does_not_claim_password_is_wrong():
    category,message=database_failure(TimeoutError('connection timed out'))
    assert category=='database_timeout'
    assert 'password' not in message.lower()

def test_database_dependency_returns_safe_timeout_response(monkeypatch):
    from fastapi import HTTPException
    from app import database
    class FakeSession:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def rollback(self):pass
    monkeypatch.setattr(database,'engine',SimpleNamespace())
    monkeypatch.setattr(database,'SessionLocal',FakeSession)
    dependency=database.get_db();next(dependency)
    with pytest.raises(HTTPException) as caught:
        dependency.throw(OperationalError('SELECT 1',None,TimeoutError('connection timeout expired PRIVATE-PASSWORD')))
    assert caught.value.status_code==503
    assert caught.value.headers['X-Database-Error']=='database_timeout'
    assert 'PRIVATE-PASSWORD' not in caught.value.detail

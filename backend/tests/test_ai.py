from types import SimpleNamespace
import httpx
import pytest
from app import ai
from app.schemas import GenerateInput

def test_offline_admin_status(signed,monkeypatch):
    monkeypatch.setattr(ai,'installed_models',lambda:(_ for _ in ()).throw(httpx.ConnectError('offline')))
    c=signed(3,'admin');r=c.get('/api/admin/ai');assert r.status_code==200 and not r.json()['connected']
    signed();assert len(c.get('/api/assessments').json())==1
def test_generation_offline_fallback(signed,monkeypatch):
    monkeypatch.setattr(ai,'generate',lambda *args:(_ for _ in ()).throw(httpx.ConnectError('offline')))
    r=signed(2,'teacher').post('/api/ai/generate',json={'outcome_id':'3.1-test'})
    assert r.status_code==503 and 'manual' in r.json()['detail'].lower()
def test_no_unreviewed_retrieval():
    with pytest.raises(ValueError,match='reviewed'):ai.retrieve([SimpleNamespace(reviewed=False)],'binary')
def test_missing_embeddings():
    with pytest.raises(ValueError,match='embeddings'):ai.retrieve([SimpleNamespace(reviewed=True,embedding=None)],'binary')
def test_local_only_models(monkeypatch):
    monkeypatch.setattr(ai,'installed_models',lambda:[{'name':'local:4b'},{'name':'remote:cloud'},{'name':'remote','remote_host':'https://example.com'}])
    assert ai.local_models()==[{'name':'local:4b'}]
def test_malformed_ai_response(env,monkeypatch):
    monkeypatch.setattr(ai,'local_models',lambda:[{'name':'qwen3:4b-instruct'}])
    monkeypatch.setattr(ai,'retrieve',lambda *args:[SimpleNamespace(id=1,text='Binary note')])
    class FakeClient:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def post(self,*args,**kwargs):return httpx.Response(200,json={'message':{'content':'{"invalid":true}'}},request=httpx.Request('POST','http://localhost'))
    monkeypatch.setattr(ai.httpx,'Client',FakeClient)
    with env() as db:
        with pytest.raises(ValueError):ai.generate(db,GenerateInput(outcome_id='3.1-test'),SimpleNamespace(id='3.1-test',text='Binary'),[])
def test_remote_ollama_configuration_rejected():
    from app.config import Settings
    with pytest.raises(ValueError):Settings(ollama_url='https://external.example')

from types import SimpleNamespace
import httpx
import pytest
from app import ai
from app.schemas import GenerateInput

def test_model_allocation_failure_has_safe_actionable_message(monkeypatch):
    monkeypatch.setattr(ai,'local_models',lambda:[{'name':ai.settings.ollama_model}])
    monkeypatch.setattr(ai,'retrieve',lambda *_:[SimpleNamespace(id=1,text='Reviewed source note')])
    class Client:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def post(self,*args,**kwargs):return httpx.Response(500,json={'error':'PRIVATE_DETAIL failed to allocate buffer'},request=httpx.Request('POST','http://localhost/api/chat'))
    monkeypatch.setattr(ai.httpx,'Client',Client)
    with pytest.raises(ai.AISetupError) as captured:ai.generate(SimpleNamespace(get=lambda *_:None),GenerateInput(outcome_id='verified'),SimpleNamespace(id='verified',text='Reviewed conversion outcome'),[])
    assert captured.value.code=='local_model_memory'
    assert 'smaller installed model' in str(captured.value)
    assert 'PRIVATE_DETAIL' not in str(captured.value)

"""Generation setup failures must explain the blocker without spending inference quota."""
import httpx
import pytest
from sqlalchemy import select

from app import ai, models as m
from app.main import limits
from app.schemas import QuestionDraft


OUTCOME = '3.1-test'


@pytest.fixture
def installed_local_models(monkeypatch):
    monkeypatch.setattr(ai, 'local_models', lambda: [
        {'name': ai.settings.ollama_model},
        {'name': ai.settings.embedding_model + ':latest'},
    ])


def resource(env, *, reviewed=True, indexed=True, embedding_model=None):
    with env() as db:
        row = m.Resource(
            outcome_id=OUTCOME,
            title='Reviewed fixture note',
            source='Original test fixture',
            text='Binary positional values are powers of two.',
            reviewed=reviewed,
            embedding=[1.0, 0.0] if indexed else None,
            embedding_model=(embedding_model or ai.settings.embedding_model) if indexed else None,
        )
        db.add(row)
        db.commit()
        return row.id


def test_readiness_is_staff_only(signed):
    response = signed().get('/api/ai/readiness', params={'outcome_id': OUTCOME})
    assert response.status_code == 403


def test_unverified_outcomes_explain_blocker_without_spending_quota(signed, env, monkeypatch):
    with env() as db:
        db.get(m.Outcome, OUTCOME).verified = False
        db.commit()
    def should_not_discover():
        raise AssertionError('An unverified outcome should be rejected before AI discovery')
    monkeypatch.setattr(ai, 'local_models', should_not_discover)
    client = signed(2, 'teacher')
    response = client.get('/api/ai/readiness', params={'outcome_id': OUTCOME})
    assert response.status_code == 200
    assert response.json()['ready'] is False
    assert response.json()['code'] == 'outcome_unverified'
    for _ in range(5):
        assert client.post('/api/ai/generate', json={'outcome_id': OUTCOME}).status_code == 422
    assert not limits.get('ai:2')


def test_missing_embedding_model_is_named(signed, monkeypatch):
    monkeypatch.setattr(ai, 'local_models', lambda: [{'name': ai.settings.ollama_model}])
    client = signed(2, 'teacher')
    response = client.get('/api/ai/readiness', params={'outcome_id': OUTCOME})
    assert response.status_code == 200
    assert response.json()['ready'] is False
    assert response.json()['code'] == 'embedding_model_missing'
    assert ai.settings.embedding_model in response.json()['message']


def test_ollama_offline_is_distinguished(signed, monkeypatch):
    def unavailable():
        raise httpx.ConnectError('Local test transport unavailable')
    monkeypatch.setattr(ai, 'local_models', unavailable)
    response = signed(2, 'teacher').get('/api/ai/readiness', params={'outcome_id': OUTCOME})
    assert response.status_code == 200
    assert response.json()['code'] == 'ollama_unavailable'
    assert response.json()['ready'] is False


def test_instruction_model_missing_is_distinguished(signed, monkeypatch):
    monkeypatch.setattr(ai, 'local_models', lambda: [{'name': ai.settings.embedding_model + ':latest'}])
    response = signed(2, 'teacher').get('/api/ai/readiness', params={'outcome_id': OUTCOME})
    assert response.status_code == 200
    assert response.json()['code'] == 'instruction_model_missing'


def test_reviewed_notes_without_vectors_explain_indexing_step(signed, env, installed_local_models):
    resource(env, indexed=False)
    response = signed(2, 'teacher').get('/api/ai/readiness', params={'outcome_id': OUTCOME})
    assert response.status_code == 200
    assert response.json()['ready'] is False
    assert response.json()['code'] == 'resources_not_indexed'
    assert 'index' in response.json()['message'].lower()


def test_stale_embedding_model_is_not_ready(signed, env, installed_local_models):
    resource(env, embedding_model='previous-embedding-model')
    response = signed(2, 'teacher').get('/api/ai/readiness', params={'outcome_id': OUTCOME})
    assert response.status_code == 200
    assert response.json()['ready'] is False
    assert response.json()['code'] == 'resources_not_indexed'


def test_unreviewed_notes_cannot_enable_generation(signed, env, installed_local_models):
    resource(env, reviewed=False)
    response = signed(2, 'teacher').get('/api/ai/readiness', params={'outcome_id': OUTCOME})
    assert response.status_code == 200
    assert response.json()['ready'] is False


def test_repeated_setup_failures_do_not_trigger_generation_rate_limit(signed, monkeypatch):
    monkeypatch.setattr(ai, 'local_models', lambda: [{'name': ai.settings.ollama_model}])
    client = signed(2, 'teacher')
    for _ in range(5):
        response = client.post('/api/ai/generate', json={'outcome_id': OUTCOME})
        assert response.status_code == 503, response.text
        assert response.json()['error_code'] == 'embedding_model_missing'
        assert ai.settings.embedding_model in response.json()['detail']
    assert not limits.get('ai:2')


def test_ready_status_requires_reviewed_current_vectors(signed, env, installed_local_models):
    resource(env)
    response = signed(2, 'teacher').get('/api/ai/readiness', params={'outcome_id': OUTCOME})
    assert response.status_code == 200
    assert response.json()['ready'] is True
    assert response.json()['code'] == 'ready'


def test_real_generation_attempts_are_still_limited_and_stay_drafts(signed, env, installed_local_models, monkeypatch):
    rid = resource(env)
    draft = QuestionDraft(
        outcome_id=OUTCOME, kind='mcq', difficulty='medium',
        prompt='Which binary value represents decimal fifteen?',
        options=[{'id':k,'text':v} for k,v in zip('ABCD',['1111','1110','1101','1100'])],
        key={'answer':'A'}, explanation='Eight plus four plus two plus one equals fifteen.',
        sources=[rid],
    )
    calls = []
    def generated(*args):
        calls.append(True)
        return draft
    monkeypatch.setattr(ai, 'generate', generated)
    client = signed(2, 'teacher')
    for _ in range(3):
        response = client.post('/api/ai/generate', json={'outcome_id': OUTCOME})
        assert response.status_code == 200, response.text
        assert response.json()['status'] == 'draft'
        with env() as db:
            assert db.get(m.Question, response.json()['id']).status == 'draft'
    response = client.post('/api/ai/generate', json={'outcome_id': OUTCOME})
    assert response.status_code == 429
    assert 1 <= int(response.headers['Retry-After']) <= 60
    assert len(calls) == 3


def test_generation_exception_details_are_not_written_to_log(signed, env, installed_local_models, monkeypatch):
    resource(env)
    secret_text = 'PRIVATE-STUDENT-ANSWER-DO-NOT-LOG'
    def fail_generation(*args):
        raise ValueError(secret_text)
    monkeypatch.setattr(ai, 'generate', fail_generation)
    response = signed(2, 'teacher').post('/api/ai/generate', json={'outcome_id': OUTCOME})
    assert response.status_code == 503
    assert secret_text not in response.text
    with env() as db:
        logs = db.scalars(select(m.GenerationLog)).all()
        assert logs
        assert all(secret_text not in row.status for row in logs)

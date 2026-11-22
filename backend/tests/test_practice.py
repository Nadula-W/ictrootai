"""Practice never exposes marking material before a student's submission.

Integration tests use the existing explicit disposable PostgreSQL/schema fixture.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier, Lock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app import models as m
from app.main import app
from app.practice import revision_summary


def submit(client, value='B', request_id=None, question_id=1):
    return client.post(f'/api/practice/{question_id}/submit', json={'value': value, 'request_id': str(request_id or uuid4())})


def new_question(db, *, kind='short', outcome_id='3.1-test', status='approved', difficulty='medium'):
    question = m.Question(outcome_id=outcome_id, kind=kind, difficulty=difficulty, prompt='Explain this approved practice concept.', options=[], key={'answer': 'An approved expected answer'}, explanation='This is the approved explanation for the concept.', status=status, sources=[], author_id=2, rubric=[{'criterion': 'Accurate explanation', 'weight': 1}] if kind in ('short', 'structured') else [])
    db.add(question)
    db.commit()
    return question.id


def test_practice_authentication_and_roles(client, signed):
    assert client.get('/api/practice').status_code == 401
    signed(2, 'teacher')
    assert client.get('/api/practice').status_code == 403
    assert client.get('/api/revision').status_code == 403
    assert submit(client).status_code == 403


def test_practice_hides_keys_and_option_misconceptions(signed):
    client = signed()
    result = client.get('/api/practice').json()
    question = result['questions'][0]
    assert question['id'] == 1
    assert set(question) == {'id', 'outcome_id', 'kind', 'difficulty', 'prompt', 'options', 'language', 'language_notice'}
    assert all(set(option) == {'id', 'text'} for option in question['options'])
    assert 'Place value confusion' not in str(result)
    assert client.get('/api/practice?limit=11').status_code == 422
    assert client.get('/api/practice?limit=0').status_code == 422
    assert client.get('/api/practice?difficulty=invalid').status_code == 422


def test_only_approved_verified_questions_are_available(signed, env):
    with env() as db:
        draft = new_question(db, status='draft')
        db.add(m.Outcome(id='unverified', unit_id=3, subtopic='Fixture', competency='Fixture', level='3.1', text='Unverified fixture outcome', source_page=21, verified=False))
        db.commit()
        unverified = new_question(db, outcome_id='unverified')
        approved = new_question(db)
    client = signed()
    ids = {question['id'] for question in client.get('/api/practice').json()['questions']}
    assert ids == {1, approved}
    assert submit(client, question_id=draft).status_code == 404
    assert submit(client, question_id=unverified).status_code == 404
    assert client.get('/api/practice?outcome_id=unknown').json()['questions'] == []
    assert [question['id'] for question in client.get('/api/practice?difficulty=easy').json()['questions']] == [1]


def test_practice_submission_persists_feedback_and_question_stays_immutable(signed, env):
    client = signed()
    response = submit(client)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['score'] == 1 and not result['pending']
    assert result['correct_answer'] == {'answer': 'B'}
    assert result['explanation'] == '8 plus 4 plus 1 equals 13.'
    with env() as db:
        answer = db.get(m.PracticeAnswer, result['id'])
        assert (answer.student_id, answer.question_id, answer.value, answer.score) == (1, 1, 'B', 1)
        question = db.get(m.Question, 1)
        assert question.status == 'approved' and question.key == {'answer': 'B'}


def test_practice_exact_retries_are_idempotent_and_changed_payload_conflicts(signed, env):
    client = signed()
    request_id = uuid4()
    first = submit(client, request_id=request_id)
    again = submit(client, request_id=request_id)
    assert first.json() == again.json()
    assert submit(client, value='A', request_id=request_id).status_code == 409
    assert submit(client, question_id=999, request_id=request_id).status_code == 409
    with env() as db:
        assert db.scalar(select(func.count()).select_from(m.PracticeAnswer)) == 1


def test_request_ids_are_student_scoped_and_revision_is_private(signed, env):
    client = signed()
    request_id = uuid4()
    first = submit(client, value='A', request_id=request_id).json()
    signed(5, 'student')
    assert client.get('/api/revision').json()['outcomes'] == []
    second = submit(client, value='B', request_id=request_id).json()
    assert first['id'] != second['id'] and second['score'] == 1
    assert client.post(f"/api/teacher/practice/{first['id']}/review", json={'score': 1, 'reason': 'Trying another student response'}).status_code == 403
    with env() as db:
        assert db.scalar(select(func.count()).select_from(m.PracticeAnswer)) == 2


def test_submission_validation_rejects_invalid_options_and_request_ids(signed):
    client = signed()
    assert submit(client, value='Z').status_code == 422
    assert submit(client, value='B' * 10001).status_code == 422
    assert client.post('/api/practice/1/submit', json={'value': 'B', 'request_id': 'invalid'}).status_code == 422
    assert client.post('/api/practice/1/submit', json={'value': 'B'}).status_code == 422


def test_descriptive_practice_is_pending_and_excluded_from_accuracy(signed, env):
    with env() as db:
        question_id = new_question(db)
    client = signed()
    feedback = submit(client, value='My explanation', question_id=question_id).json()
    assert feedback['score'] is None and feedback['pending']
    assert feedback['rubric'] and 'Teacher review' in feedback['reason']
    summary = client.get('/api/revision').json()['outcomes'][0]
    assert summary['accuracy'] is None and summary['recent_accuracy'] is None
    assert summary['marked_attempts'] == 0 and summary['pending'] == 1


def test_review_requires_owned_class_membership_and_keeps_audit(signed, env):
    with env() as db:
        question_id = new_question(db)
    client = signed()
    answer_id = submit(client, value='Partial explanation', question_id=question_id).json()['id']
    signed(4, 'teacher')
    assert client.get('/api/teacher/practice').json() == []
    assert client.post(f'/api/teacher/practice/{answer_id}/review', json={'score': 1, 'reason': 'Not my learner'}).status_code == 404
    signed(2, 'teacher')
    assert client.get('/api/teacher/practice').json()[0]['id'] == answer_id
    for score in (0.5, 1):
        response = client.post(f'/api/teacher/practice/{answer_id}/review', json={'score': score, 'reason': 'Approved rubric criterion checked'})
        assert response.status_code == 200 and response.json()['score'] == score
    assert client.get('/api/teacher/practice').json() == []
    with env() as db:
        assert db.get(m.PracticeAnswer, answer_id).reviewed_by == 2
        assert [review.score for review in db.scalars(select(m.PracticeReview).order_by(m.PracticeReview.id))] == [0.5, 1]
    signed()
    assert client.get('/api/revision').json()['outcomes'][0]['accuracy'] == 100


def test_teacher_cannot_review_unenrolled_student_admin_can(signed, env):
    with env() as db:
        question_id = new_question(db)
    client = signed(5, 'student')
    answer_id = submit(client, value='Explanation', question_id=question_id).json()['id']
    signed(2, 'teacher')
    assert client.post(f'/api/teacher/practice/{answer_id}/review', json={'score': 1, 'reason': 'No student membership'}).status_code == 404
    signed(3, 'admin')
    assert client.post(f'/api/teacher/practice/{answer_id}/review', json={'score': 1, 'reason': 'Administrator rubric review'}).status_code == 200
    assert client.post(f'/api/teacher/practice/{answer_id}/review', json={'score': 2, 'reason': 'Invalid mark'}).status_code == 422
    assert client.post(f'/api/teacher/practice/{answer_id}/review', json={'score': 1, 'reason': '     '}).status_code == 422


def test_single_misconception_is_tentative_and_repeated_pattern_is_counted(signed):
    client = signed()
    feedback = submit(client, value='A').json()
    assert feedback['possible_misconception'] == 'Place value confusion'
    assert 'single answer' in feedback['misconception_notice']
    assert client.get('/api/revision').json()['outcomes'][0]['possible_misconceptions'] == []
    submit(client, value='C')
    state = client.get('/api/revision').json()['outcomes'][0]
    assert state['accuracy'] == 0 and state['recommended_difficulty'] == 'easy'
    assert state['possible_misconceptions'][0]['count'] == 2
    assert 'not a diagnosis' in state['possible_misconceptions'][0]['message']


def test_revision_counts_assessment_answers_only_after_submission(signed):
    client = signed()
    attempt_id = client.post('/api/assessments/1/start').json()['id']
    client.put(f'/api/attempts/{attempt_id}/answers/1', json={'value': 'B'})
    assert client.get('/api/revision').json()['outcomes'] == []
    client.post(f'/api/attempts/{attempt_id}/submit')
    state = client.get('/api/revision').json()['outcomes'][0]
    assert state['attempts'] == 1 and state['accuracy'] == 100


def test_unseen_questions_are_prioritised(signed, env):
    with env() as db:
        question_id = new_question(db)
    client = signed()
    submit(client)
    assert client.get('/api/practice?limit=1').json()['questions'][0]['id'] == question_id


def test_reviewed_translations_cannot_inject_marking_fields(signed, env):
    with env() as db:
        db.get(m.User, 1).language = 'si'
        db.add(m.Translation(question_id=1, language='si', reviewed=True, content={'prompt': 'Reviewed display translation', 'key': {'answer': 'LEAK'}, 'rubric': [{'secret': 'LEAK'}], 'explanation': 'LEAK', 'options': [{'id': key, 'text': value, 'misconception': 'LEAK'} for key, value in zip('ABCD', ['a', 'b', 'c', 'd'])]}))
        db.commit()
    result = signed().get('/api/practice').json()
    assert result['questions'][0]['language'] == 'si'
    assert 'LEAK' not in str(result)


@pytest.mark.parametrize('values,difficulty,days', [([0, 0.5], 'easy', 1), ([1, 0.5], 'medium', 3), ([1, 1], 'hard', 7)])
def test_revision_heuristic_uses_only_marked_recent_responses(values, difficulty, days):
    now = datetime(2026, 11, 22, tzinfo=timezone.utc)
    rows = [{'outcome_id': 'test', 'text': 'A fixture outcome', 'score': score, 'created': now - timedelta(minutes=index), 'value': '', 'kind': 'short', 'options': []} for index, score in enumerate(values)]
    rows.append({**rows[0], 'score': None, 'created': now + timedelta(minutes=1)})
    summary = revision_summary(rows, now)[0]
    assert summary['recommended_difficulty'] == difficulty
    assert summary['review_interval_days'] == days
    assert summary['pending'] == 1
    assert summary['next_review_at'] == (now + timedelta(days=days)).isoformat()


def test_revision_recent_window_differs_from_lifetime_accuracy():
    now = datetime(2026, 11, 22, tzinfo=timezone.utc)
    rows = [{'outcome_id': 'test', 'text': 'A fixture outcome', 'score': 0 if index < 5 else 1, 'created': now - timedelta(days=index), 'value': '', 'kind': 'short', 'options': []} for index in range(10)]
    summary = revision_summary(rows, now)[0]
    assert summary['accuracy'] == 50 and summary['recent_accuracy'] == 0
    assert summary['recommended_difficulty'] == 'easy'


@pytest.mark.parametrize('different_payload', [False, True])
def test_concurrent_request_retries_are_transactional(signed, env, monkeypatch, different_payload):
    import app.practice as module
    client = signed()
    token = client.cookies.get('ictroot_session')
    request_id = str(uuid4())
    barrier = Barrier(2)
    lock = Lock()
    calls = 0
    original = module._existing_submission

    def simultaneous(*args):
        nonlocal calls
        result = original(*args)
        with lock:
            calls += 1
            wait = calls <= 2
        if wait:
            barrier.wait(timeout=10)
        return result

    monkeypatch.setattr(module, '_existing_submission', simultaneous)

    def send(value):
        with TestClient(app) as separate:
            separate.cookies.set('ictroot_session', token)
            return submit(separate, value=value, request_id=request_id)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(send, ['B', 'A' if different_payload else 'B']))
    assert sorted(response.status_code for response in results) == ([200, 409] if different_payload else [200, 200])
    with env() as db:
        assert db.scalar(select(func.count()).select_from(m.PracticeAnswer)) == 1
    if not different_payload:
        assert results[0].json() == results[1].json()

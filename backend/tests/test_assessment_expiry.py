"""Deadline finalization on explicit disposable PostgreSQL test schemas only."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier

import pytest
from sqlalchemy import func, select

from app import models as m
from app.assessment_lifecycle import as_utc, attempt_deadline, finalize_expired


def expired_attempt(db, *, tid=1, aid=1, student_id=1, saved='B', started=None):
    attempt = m.Attempt(id=tid, assessment_id=aid, student_id=student_id,
                        started=started or datetime.now(timezone.utc) - timedelta(hours=1), submitted=False)
    db.add(attempt)
    db.flush()
    if saved is not None:
        db.add(m.Answer(attempt_id=tid, question_id=1, value=saved))
    db.commit()
    return attempt


def foreign_attempt(db):
    db.add(m.ClassRoom(id=2, name='Private other class', teacher_id=4, grade=12, code='PRIVATE-EXPIRY'))
    db.flush()
    db.add(m.Membership(class_id=2, student_id=5))
    db.add(m.Assessment(id=2, title='Private other assessment', teacher_id=4, class_id=2,
                        duration=15, published=True))
    db.flush()
    db.add(m.AssessmentQuestion(assessment_id=2, question_id=1, position=0))
    db.flush()
    return expired_attempt(db, tid=2, aid=2, student_id=5)


def test_deadline_uses_real_utc_conversion_and_inclusive_end():
    offset = timezone(timedelta(hours=5, minutes=30))
    started = datetime(2026, 11, 22, 12, 0, tzinfo=offset)
    assert as_utc(started) == datetime(2026, 11, 22, 6, 30, tzinfo=timezone.utc)
    assert attempt_deadline(started, 15) == datetime(2026, 11, 22, 6, 45, tzinfo=timezone.utc)
    assert as_utc(datetime(2026, 11, 22, 6, 30)).tzinfo == timezone.utc


def test_unscoped_finalization_is_rejected_without_database_access():
    with pytest.raises(ValueError, match='authorized scope'):
        finalize_expired(object())


@pytest.mark.parametrize('scope', [
    {'student_id': 0}, {'student_id': True}, {'teacher_id': -1},
    {'class_ids': [0]}, {'assessment_ids': ['1']}, {'attempt_ids': [True]},
])
def test_invalid_scope_cannot_turn_into_broad_finalization(scope):
    with pytest.raises(ValueError, match='Invalid'):
        finalize_expired(object(), **scope)


@pytest.mark.parametrize('scope', [{'attempt_ids': []}, {'assessment_ids': []}, {'class_ids': []}])
def test_explicit_empty_scope_is_noop(scope):
    assert finalize_expired(object(), **scope) == []


def test_exact_deadline_finalizes_saved_answers_and_is_idempotent(env):
    moment = datetime.now(timezone.utc)
    with env() as db:
        expired_attempt(db, started=moment - timedelta(minutes=15))
        assert finalize_expired(db, student_id=1, now=moment) == [1]
        db.commit()
        assert db.get(m.Attempt, 1).submitted is True
        assert db.get(m.Answer, (1, 1)).score == 1
        assert finalize_expired(db, attempt_ids=[1], now=moment + timedelta(days=1)) == []
        assert db.scalar(select(func.count()).select_from(m.Answer)) == 1


def test_one_microsecond_before_deadline_does_not_finalize(env):
    moment = datetime.now(timezone.utc)
    with env() as db:
        expired_attempt(db, started=moment - timedelta(minutes=15))
        assert finalize_expired(db, student_id=1, now=moment - timedelta(microseconds=1)) == []
        assert db.get(m.Attempt, 1).submitted is False
        assert db.get(m.Answer, (1, 1)).score is None


def test_finalization_stays_in_callers_transaction(env):
    with env() as db:
        expired_attempt(db, saved=None)
        assert finalize_expired(db, student_id=1) == [1]
        assert db.get(m.Answer, (1, 1)).score == 0
        db.rollback()
        assert db.get(m.Attempt, 1).submitted is False
        assert db.get(m.Answer, (1, 1)) is None


def test_resume_finalizes_saved_answers_without_exposing_keys_in_attempt_payload(env, signed):
    with env() as db:
        expired_attempt(db)
    c = signed()
    response = c.get('/api/attempts/1')
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['submitted'] is True
    assert result['answers'] == {'1': 'B'}
    assert 'key' not in result['questions'][0]
    assert 'explanation' not in result['questions'][0]
    assert c.get('/api/attempts/1/results').json()['score'] == 1
    assert c.post('/api/attempts/1/submit').status_code == 409


def test_results_first_read_can_finalize_expired_attempt(env, signed):
    with env() as db:
        expired_attempt(db, saved='A')
    response = signed().get('/api/attempts/1/results')
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['score'] == 0
    assert result['items'][0]['value'] == 'A'
    assert result['items'][0]['key']['answer'] == 'B'


@pytest.mark.parametrize('path', ['/api/assessments', '/api/history', '/api/progress'])
def test_student_lists_finalize_only_their_own_elapsed_attempts(env, signed, path):
    with env() as db:
        expired_attempt(db)
        foreign_attempt(db)
    response = signed().get(path)
    assert response.status_code == 200, response.text
    with env() as db:
        assert db.get(m.Attempt, 1).submitted is True
        assert db.get(m.Attempt, 2).submitted is False
        assert db.get(m.Answer, (1, 1)).score == 1
        assert db.get(m.Answer, (2, 1)).score is None


def test_blank_answers_are_final_zero_and_descriptive_saved_answers_remain_pending(env, signed):
    with env() as db:
        db.add(m.Question(id=2, outcome_id='3.1-test', kind='short', difficulty='medium',
                          prompt='Explain the binary place values', options=[], key={'answer': 'Powers of two'},
                          explanation='Place values are powers of two.', status='approved', author_id=2,
                          sources=[], rubric=[{'criterion': 'Powers of two', 'weight': 1}]))
        db.flush()
        db.add(m.AssessmentQuestion(assessment_id=1, question_id=2, position=1))
        expired_attempt(db, saved=None)
        db.add(m.Answer(attempt_id=1, question_id=2, value='Each position is a power of two.'))
        db.commit()
    response = signed().get('/api/attempts/1/results')
    assert response.status_code == 200, response.text
    result = response.json()
    by_id = {row['question_id']: row for row in result['items']}
    assert result['pending'] == 1
    assert result['total'] == 2
    assert by_id[1]['score'] == 0
    assert by_id[1]['value'] == ''
    assert by_id[1]['reason'] == 'No answer submitted'
    assert by_id[2]['score'] is None
    assert 'Teacher review required' in by_id[2]['reason']


def test_late_save_is_rejected_and_cannot_replace_saved_answer(env, signed):
    with env() as db:
        expired_attempt(db, saved='A')
    c = signed()
    assert c.put('/api/attempts/1/answers/1', json={'value': 'B'}).status_code == 409
    result = c.get('/api/attempts/1/results').json()
    assert result['items'][0]['value'] == 'A'
    assert result['score'] == 0
    assert c.put('/api/attempts/1/answers/1', json={'value': 'B'}).status_code == 409
    assert c.post('/api/attempts/1/submit').status_code == 409


def test_unauthorized_foreign_reads_cannot_finalize_or_reveal_an_attempt(env, signed):
    with env() as db:
        expired_attempt(db)
    c = signed(5, 'student')
    assert c.get('/api/attempts/1').status_code == 404
    assert c.get('/api/attempts/1/results').status_code == 404
    c = signed(4, 'teacher')
    assert c.get('/api/attempts/1').status_code == 404
    assert c.get('/api/attempts/1/results').status_code == 404
    assert c.get('/api/classes/1/students').status_code == 404
    assert c.get('/api/classes/1/students/1/progress').status_code == 404
    assert c.get('/api/teacher/submissions').json() == []
    with env() as db:
        assert db.get(m.Attempt, 1).submitted is False
        assert db.get(m.Answer, (1, 1)).score is None


def test_nonmember_progress_path_does_not_finalize_another_students_answers(env, signed):
    with env() as db:
        expired_attempt(db, student_id=5)
    assert signed(2, 'teacher').get('/api/classes/1/students/5/progress').status_code == 404
    with env() as db:
        assert db.get(m.Attempt, 1).submitted is False


@pytest.mark.parametrize('path', [
    '/api/teacher/submissions', '/api/assessments', '/api/classes/1/students',
    '/api/classes/1/students/1/progress',
])
def test_teacher_reads_finalize_only_authorized_elapsed_work(env, signed, path):
    with env() as db:
        expired_attempt(db)
        foreign_attempt(db)
    response = signed(2, 'teacher').get(path)
    assert response.status_code == 200, response.text
    with env() as db:
        assert db.get(m.Attempt, 1).submitted is True
        assert db.get(m.Attempt, 2).submitted is False
    if path == '/api/teacher/submissions':
        assert response.json() == [{'id': 1, 'student': 'student1', 'title': 'Number systems', 'score': 1, 'total': 1, 'pending': 0}]


def test_admin_report_can_finalize_all_visible_classes(env, signed):
    with env() as db:
        expired_attempt(db)
        foreign_attempt(db)
    response = signed(3, 'admin').get('/api/teacher/submissions')
    assert response.status_code == 200
    assert {row['id'] for row in response.json()} == {1, 2}
    with env() as db:
        assert db.get(m.Attempt, 1).submitted is True
        assert db.get(m.Attempt, 2).submitted is True


def test_overlapping_deadline_readers_mark_once_under_the_same_attempt_lock(env, monkeypatch):
    from app import assessment_lifecycle
    with env() as db:
        expired_attempt(db)
    original_mark = assessment_lifecycle.mark
    calls = []

    def counting_mark(question, value):
        calls.append((question.id, value))
        return original_mark(question, value)

    monkeypatch.setattr(assessment_lifecycle, 'mark', counting_mark)
    barrier = Barrier(2)

    def finish(scope):
        with env() as db:
            barrier.wait(timeout=5)
            changed = finalize_expired(db, **scope)
            db.commit()
            return changed

    with ThreadPoolExecutor(max_workers=2) as workers:
        jobs = [workers.submit(finish, scope) for scope in ({'student_id': 1}, {'class_ids': [1]})]
        results = [job.result(timeout=15) for job in jobs]
    assert sorted(len(result) for result in results) == [0, 1]
    assert calls == [(1, 'B')]
    with env() as db:
        assert db.get(m.Attempt, 1).submitted is True
        assert db.get(m.Answer, (1, 1)).score == 1


def test_existing_teacher_review_is_not_overwritten_by_repeated_deadline_reads(env, signed):
    with env() as db:
        expired_attempt(db)
    c = signed()
    assert c.get('/api/attempts/1/results').status_code == 200
    signed(2, 'teacher')
    assert c.post('/api/attempts/1/answers/1/review', json={
        'score': 0.5, 'reason': 'Reviewed partial-credit decision after discussion',
    }).status_code == 200
    assert c.get('/api/teacher/submissions').json()[0]['score'] == 0.5
    assert c.get('/api/attempts/1/results').json()['score'] == 0.5
    with env() as db:
        assert db.get(m.Answer, (1, 1)).reviewed_by == 2

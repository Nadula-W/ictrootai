"""Read-only question plans and class-scoped reports on disposable PostgreSQL.

The shared env fixture requires explicit TEST_DATABASE_URL and owns only its
generated schema. No test uses the configured application database.
"""
from contextlib import contextmanager

import pytest
from pydantic import ValidationError
from sqlalchemy import event, func, select

from app import models as m
from app.assessment_tools import AssessmentPreview, class_students, student_class_progress


def add_outcome(db, oid='other-outcome', unit_id=3, verified=True):
    db.add(m.Outcome(id=oid, unit_id=unit_id, subtopic='Fixture topic', competency='Fixture competency',
                     level=f'{unit_id}.1', text=f'Fixture learning outcome {oid}', source_page=21, verified=verified))
    db.flush()


def add_question(db, qid, oid='3.1-test', kind='mcq', difficulty='easy', status='approved'):
    db.add(m.Question(id=qid, outcome_id=oid, kind=kind, difficulty=difficulty,
                      prompt=f'Fixture question {qid}', options=[
                          {'id': 'A', 'text': 'Wrong option', 'misconception': 'Place value confusion'},
                          {'id': 'B', 'text': 'Correct option'},
                          {'id': 'C', 'text': 'Another option'}, {'id': 'D', 'text': 'Fourth option'},
                      ] if kind == 'mcq' else [],
                      key={'answer': 'B'}, explanation='Private fixture explanation', status=status,
                      author_id=2, sources=[], rubric=[{'criterion': 'Fixture criterion'}] if kind in ('short', 'structured') else []))
    db.flush()


def report_data(db):
    add_outcome(db)
    add_question(db, 2)
    add_question(db, 3, oid='other-outcome', kind='short')
    db.add(m.ClassRoom(id=2, name='Another teacher class', teacher_id=4, grade=12, code='OTHERCLASS'))
    db.flush()
    db.add_all([m.Membership(class_id=2, student_id=1), m.Membership(class_id=1, student_id=5)])
    for aid, cid, published in [(2, 1, True), (3, 2, True), (4, 1, False)]:
        db.add(m.Assessment(id=aid, title=f'Fixture assessment {aid}', teacher_id=2 if cid == 1 else 4,
                            class_id=cid, duration=15, published=published))
    db.flush()
    for aid, qid, position in [(2, 2, 0), (2, 3, 1), (3, 1, 0), (4, 1, 0)]:
        db.add(m.AssessmentQuestion(assessment_id=aid, question_id=qid, position=position))
    for tid, aid, uid, submitted in [(1, 1, 1, True), (2, 2, 1, True), (3, 3, 1, True),
                                      (4, 4, 1, False), (5, 1, 5, True)]:
        db.add(m.Attempt(id=tid, assessment_id=aid, student_id=uid, submitted=submitted))
    db.flush()
    for tid, qid, score, value in [(1, 1, 0., 'A'), (2, 2, 0., 'A'), (2, 3, None, 'Descriptive answer'),
                                    (3, 1, 1., 'B'), (4, 1, 1., 'B'), (5, 1, 1., 'B')]:
        db.add(m.Answer(attempt_id=tid, question_id=qid, score=score, value=value, reason='Fixture result'))
    db.commit()


@contextmanager
def count_reads(db):
    connection = db.connection()
    statements = []

    def record(_connection, _cursor, statement, _parameters, _context, _many):
        if statement.lstrip().upper().startswith('SELECT'):
            statements.append(statement)

    event.listen(connection, 'before_cursor_execute', record)
    try:
        yield statements
    finally:
        event.remove(connection, 'before_cursor_execute', record)


@pytest.mark.parametrize('payload', [
    {'count': 0}, {'count': 101}, {'unit_ids': [15]}, {'unit_ids': [0]},
    {'unit_ids': [3, 3]}, {'outcome_ids': ['x', 'x']}, {'outcome_ids': ['x' * 121]},
    {'outcome_ids': [str(i) for i in range(101)]}, {'kinds': ['mcq', 'mcq']},
    {'kinds': ['python_execution']}, {'difficulty': 'extreme'}, {'style': 'official'},
    {'style': 'paper_i', 'kinds': ['short']}, {'style': 'paper_ii', 'kinds': ['mcq']},
    {'unknown_filter': True},
])
def test_preview_contract_bounds_and_compatible_styles(payload):
    with pytest.raises(ValidationError):
        AssessmentPreview(**payload)


def test_preview_requires_staff(client, signed):
    assert client.post('/api/assessments/preview', json={'count': 1}).status_code == 401
    signed()
    assert client.post('/api/assessments/preview', json={'count': 1}).status_code == 403
    signed(2, 'teacher')
    assert client.post('/api/assessments/preview', json={'count': 1}).status_code == 200
    signed(3, 'admin')
    assert client.post('/api/assessments/preview', json={'count': 1}).status_code == 200


def test_preview_balances_requested_outcomes_deterministically_without_writes(env, signed):
    with env() as db:
        add_outcome(db, 'topic-b')
        add_outcome(db, 'topic-c')
        for qid in range(2, 6):
            add_question(db, qid)
        for qid in range(6, 9):
            add_question(db, qid, oid='topic-b')
        add_question(db, 9, oid='topic-c')
        db.commit()
        before = db.scalar(select(func.count()).select_from(m.Assessment))
    c = signed(2, 'teacher')
    payload = {'outcome_ids': ['3.1-test', 'topic-b', 'topic-c'], 'count': 5}
    first = c.post('/api/assessments/preview', json=payload)
    second = c.post('/api/assessments/preview', json=payload)
    assert first.status_code == 200, first.text
    result = first.json()
    assert result == second.json()
    assert result['question_ids'] == [1, 6, 9, 2, 7]
    assert result['count'] == 5
    assert result['available_count'] == 9
    assert result['coverage']['represented_outcome_count'] == 3
    assert [row['selected'] for row in result['coverage']['per_outcome']] == [2, 2, 1]
    assert 'not an official examination blueprint' in result['practice_notice']
    assert all('key' not in q and 'explanation' not in q for q in result['questions'])
    with env() as db:
        assert db.scalar(select(func.count()).select_from(m.Assessment)) == before


def test_preview_excludes_drafts_rejected_and_unverified_outcomes(env, signed):
    with env() as db:
        add_outcome(db, 'unverified', verified=False)
        add_question(db, 2, status='draft')
        add_question(db, 3, status='rejected')
        add_question(db, 4, oid='unverified')
        db.commit()
    c = signed(2, 'teacher')
    response = c.post('/api/assessments/preview', json={'count': 2})
    assert response.status_code == 422
    detail = response.json()['detail']
    assert detail['available_count'] == 1
    assert detail['requested_count'] == 2
    assert detail['shortage'] == 1
    assert c.post('/api/assessments/preview', json={'count': 1}).json()['question_ids'] == [1]
    response = c.post('/api/assessments/preview', json={'outcome_ids': ['unverified'], 'count': 1})
    assert response.status_code == 422
    assert response.json()['detail']['unavailable_outcome_ids'] == ['unverified']


def test_preview_filters_units_outcomes_difficulty_and_formats(env, signed):
    with env() as db:
        db.add(m.Unit(id=4, version_id='test', name='Digital circuits', grade=12, verified=True))
        db.flush()
        add_outcome(db, 'circuit-outcome', unit_id=4)
        add_question(db, 2, kind='structured', difficulty='hard')
        add_question(db, 3, kind='short', difficulty='medium')
        add_question(db, 4, kind='number')
        add_question(db, 5, difficulty='hard')
        add_question(db, 6, oid='circuit-outcome')
        db.commit()
    c = signed(2, 'teacher')
    response = c.post('/api/assessments/preview', json={
        'unit_ids': [3], 'outcome_ids': ['3.1-test'], 'difficulty': 'hard', 'kinds': ['mcq'], 'count': 1,
    })
    assert response.status_code == 200, response.text
    assert response.json()['question_ids'] == [5]
    assert response.json()['available_count'] == 1
    assert c.post('/api/assessments/preview', json={'unit_ids': [4], 'count': 1}).json()['question_ids'] == [6]
    assert c.post('/api/assessments/preview', json={
        'unit_ids': [4], 'outcome_ids': ['3.1-test'], 'count': 1,
    }).status_code == 422
    unknown = c.post('/api/assessments/preview', json={'outcome_ids': ['not-a-real-outcome'], 'count': 1})
    assert unknown.status_code == 422


def test_practice_paper_styles_select_only_matching_approved_formats(env, signed):
    with env() as db:
        add_question(db, 2, kind='short')
        add_question(db, 3, kind='structured')
        add_question(db, 4, kind='number')
        add_question(db, 5, kind='short', status='draft')
        db.commit()
    c = signed(2, 'teacher')
    paper_i = c.post('/api/assessments/preview', json={'style': 'paper_i', 'count': 1})
    assert paper_i.status_code == 200
    assert paper_i.json()['question_ids'] == [1]
    paper_ii = c.post('/api/assessments/preview', json={'style': 'paper_ii', 'count': 2})
    assert paper_ii.status_code == 200
    assert paper_ii.json()['question_ids'] == [2, 3]
    assert c.post('/api/assessments/preview', json={'style': 'paper_ii', 'count': 3}).status_code == 422


def test_plan_reports_missing_topic_coverage_instead_of_claiming_complete(env, signed):
    with env() as db:
        add_outcome(db, 'empty-topic')
        db.commit()
    result = signed(2, 'teacher').post('/api/assessments/preview', json={
        'outcome_ids': ['3.1-test', 'empty-topic'], 'count': 1,
    }).json()
    assert result['count'] == 1
    assert result['coverage']['requested_outcome_count'] == 2
    assert result['coverage']['represented_outcome_count'] == 1
    assert result['coverage']['per_outcome'][1] == {'outcome_id': 'empty-topic', 'available': 0, 'selected': 0}


def test_class_reports_require_owner_or_admin_and_hide_nonmembers(env, signed):
    with env() as db:
        report_data(db)
    c = signed(4, 'teacher')
    assert c.get('/api/classes/1/students').status_code == 404
    assert c.get('/api/classes/1/students/1/progress').status_code == 404
    c = signed()
    assert c.get('/api/classes/1/students').status_code == 403
    assert c.get('/api/classes/1/students/1/progress').status_code == 403
    c = signed(2, 'teacher')
    assert c.get('/api/classes/2/students').status_code == 404
    assert c.get('/api/classes/1/students/999/progress').status_code == 404
    c = signed(3, 'admin')
    assert c.get('/api/classes/1/students').status_code == 200
    assert c.get('/api/classes/2/students/1/progress').status_code == 200


def test_roster_scopes_marks_to_class_and_excludes_pending_and_unsubmitted_answers(env, signed):
    with env() as db:
        report_data(db)
    response = signed(2, 'teacher').get('/api/classes/1/students')
    assert response.status_code == 200, response.text
    rows = {row['id']: row for row in response.json()['students']}
    assert set(rows) == {1, 5}
    assert rows[1]['started_assessments'] == 3
    assert rows[1]['submitted_assessments'] == 2
    assert rows[1]['marked_answers'] == 2
    assert rows[1]['pending_answers'] == 1
    assert rows[1]['accuracy'] == 0
    assert rows[5]['accuracy'] == 100


def test_student_progress_is_class_scoped_with_tentative_repeated_evidence(env, signed):
    with env() as db:
        report_data(db)
    response = signed(2, 'teacher').get('/api/classes/1/students/1/progress')
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['student']['id'] == 1
    assert result['submitted_assessments'] == 2
    assert result['marked_answers'] == 2
    assert result['pending_answers'] == 1
    assert result['accuracy'] == 0
    assert result['recommended_difficulty'] == 'easy'
    by_id = {row['outcome_id']: row for row in result['outcomes']}
    assert by_id['3.1-test']['answered'] == 2
    assert by_id['other-outcome']['accuracy'] is None
    assert by_id['other-outcome']['pending_answers'] == 1
    assert [row['outcome_id'] for row in result['weak_outcomes']] == ['3.1-test']
    assert len(result['possible_misconceptions']) == 1
    evidence = result['possible_misconceptions'][0]
    assert evidence['evidence_count'] == 2
    assert evidence['question_count'] == 2
    assert 'tentative' in evidence['notice']
    assert 'not a diagnosis' in evidence['notice']
    assert 'key' not in response.text and 'Private fixture explanation' not in response.text


def test_single_wrong_answer_does_not_create_repeated_misconception(env, signed):
    with env() as db:
        report_data(db)
        db.get(m.Answer, (2, 2)).score = 1
        db.commit()
    result = signed(2, 'teacher').get('/api/classes/1/students/1/progress').json()
    assert result['possible_misconceptions'] == []
    assert result['accuracy'] == 50


def test_fractional_teacher_marks_are_included_and_pending_marks_are_excluded(env, signed):
    with env() as db:
        report_data(db)
        db.get(m.Answer, (1, 1)).score = 1
        db.get(m.Answer, (2, 2)).score = 0.5
        db.commit()
    c = signed(2, 'teacher')
    result = c.get('/api/classes/1/students/1/progress').json()
    assert result['accuracy'] == 75
    assert result['marked_answers'] == 2
    assert result['pending_answers'] == 1
    assert result['recommended_difficulty'] == 'medium'
    roster = c.get('/api/classes/1/students').json()['students']
    assert next(row for row in roster if row['id'] == 1)['accuracy'] == 75


def test_no_marks_yet_is_unknown_accuracy_not_zero(env, signed):
    with env() as db:
        db.add(m.Membership(class_id=1, student_id=5))
        db.commit()
    c = signed(2, 'teacher')
    result = c.get('/api/classes/1/students/5/progress').json()
    assert result['accuracy'] is None
    assert result['submitted_assessments'] == 0
    assert result['outcomes'] == []
    assert result['possible_misconceptions'] == []
    rows = c.get('/api/classes/1/students').json()['students']
    assert next(row for row in rows if row['id'] == 5)['accuracy'] is None
    assert c.get('/api/classes/1/students/4/progress').status_code == 404


def test_roster_and_progress_reads_are_batched(env):
    with env() as db:
        report_data(db)
        teacher = db.get(m.User, 2)
        with count_reads(db) as roster_queries:
            class_students(1, teacher, db)
        assert len(roster_queries) == 3
        with count_reads(db) as progress_queries:
            student_class_progress(1, 1, teacher, db)
        assert len(progress_queries) == 4
        assert not any('questions.key' in sql or 'questions.explanation' in sql for sql in progress_queries)

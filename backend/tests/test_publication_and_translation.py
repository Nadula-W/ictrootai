"""Regressions for publication authorization and legacy translation privacy."""
import pytest
from sqlalchemy import select

from app import models as m


def legacy_translation(db, content):
    db.add(m.Translation(question_id=1, language='si', reviewed=True, content=content))
    db.commit()


def translated_options():
    return [{'id': oid, 'text': f'Translated option {oid}', 'misconception': 'PRIVATE_TRANSLATION_LABEL'} for oid in 'ABCD']


def test_legacy_translation_cannot_inject_marking_material_or_identifiers(env, signed):
    with env() as db:
        legacy_translation(db, {
            'prompt': 'Translated question prompt', 'options': translated_options(),
            'key': {'answer': 'PRIVATE_TRANSLATION_KEY'}, 'explanation': 'PRIVATE_TRANSLATION_EXPLANATION',
            'rubric': [{'criterion': 'PRIVATE_TRANSLATION_RUBRIC'}], 'sources': ['PRIVATE_TRANSLATION_SOURCE'],
            'id': 9999, 'outcome_id': 'PRIVATE_TRANSLATION_OUTCOME', 'kind': 'structured', 'status': 'draft',
        })
    c = signed()
    attempt_id = c.post('/api/assessments/1/start').json()['id']
    response = c.get(f'/api/attempts/{attempt_id}?language=si')
    assert response.status_code == 200, response.text
    question = response.json()['questions'][0]
    assert question['language'] == 'si'
    assert question['prompt'] == 'Translated question prompt'
    assert question['id'] == 1
    assert question['kind'] == 'mcq'
    assert question['outcome_id'] == '3.1-test'
    assert question['status'] == 'approved'
    assert [option['id'] for option in question['options']] == list('ABCD')
    assert all(set(option) == {'id', 'text'} for option in question['options'])
    assert not any(field in question for field in ('key', 'explanation', 'rubric', 'sources'))
    assert 'PRIVATE_TRANSLATION_' not in response.text
    signed(2, 'teacher')
    response = c.get(f'/api/attempts/{attempt_id}?language=si')
    assert response.status_code == 200
    staff_question = response.json()['questions'][0]
    assert staff_question['key'] == {'answer': 'B'}
    assert staff_question['explanation'] == '8 plus 4 plus 1 equals 13.'
    assert staff_question['id'] == 1
    assert 'PRIVATE_TRANSLATION_' not in response.text


@pytest.mark.parametrize('content', [
    {'prompt': 'Translated prompt', 'options': [{'id': x, 'text': x} for x in 'BACD']},
    {'prompt': 'Translated prompt', 'options': [{'id': x, 'text': x} for x in 'ABCE']},
    {'prompt': 'Translated prompt', 'options': [{'id': x, 'text': x} for x in 'ABC']},
    {'prompt': 'Translated prompt', 'options': [{'id': x, 'text': None} for x in 'ABCD']},
    {'prompt': 1234, 'options': translated_options()},
    {'prompt': '     ', 'options': translated_options()},
    {'prompt': 'Translated prompt', 'options': 'not an option array'},
    ['not', 'a', 'display', 'object'],
])
def test_invalid_reviewed_legacy_display_falls_back_to_original_english(env, signed, content):
    with env() as db:
        legacy_translation(db, content)
    c = signed()
    attempt_id = c.post('/api/assessments/1/start').json()['id']
    response = c.get(f'/api/attempts/{attempt_id}?language=si')
    assert response.status_code == 200, response.text
    question = response.json()['questions'][0]
    assert question['language'] == 'en'
    assert question['prompt'] == 'Which number is binary thirteen?'
    assert question['options'][0] == {'id': 'A', 'text': '1110'}
    assert 'invalid' in question['language_notice']
    assert 'key' not in question


def test_publishing_is_owner_or_admin_only_and_does_not_mutate_question_selection(env, signed):
    with env() as db:
        db.get(m.Assessment, 1).published = False
        before = [(row.question_id, row.position) for row in db.scalars(select(m.AssessmentQuestion))]
        db.commit()
    c = signed()
    assert c.get('/api/assessments').json() == []
    assert c.post('/api/assessments/1/publish').status_code == 403
    signed(4, 'teacher')
    assert c.post('/api/assessments/1/publish').status_code == 404
    signed(2, 'teacher')
    first = c.post('/api/assessments/1/publish')
    second = c.post('/api/assessments/1/publish')
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json() == {'id': 1, 'published': True, 'questions': 1}
    signed()
    assert c.get('/api/assessments').json()[0]['published'] is True
    with env() as db:
        assert [(row.question_id, row.position) for row in db.scalars(select(m.AssessmentQuestion))] == before
        assert db.get(m.Question, 1).status == 'approved'
        assert db.get(m.Question, 1).key == {'answer': 'B'}


@pytest.mark.parametrize('status', ['draft', 'rejected'])
def test_publication_rejects_any_unapproved_question(env, signed, status):
    with env() as db:
        db.get(m.Assessment, 1).published = False
        db.get(m.Question, 1).status = status
        db.commit()
    response = signed(2, 'teacher').post('/api/assessments/1/publish')
    assert response.status_code == 422
    with env() as db:
        assert db.get(m.Assessment, 1).published is False


def test_empty_assessment_cannot_be_published(env, signed):
    with env() as db:
        db.add(m.Assessment(id=2, title='Empty draft', teacher_id=2, class_id=1, duration=15, published=False))
        db.commit()
    assert signed(2, 'teacher').post('/api/assessments/2/publish').status_code == 422
    with env() as db:
        assert db.get(m.Assessment, 2).published is False


def test_publication_checks_class_ownership_even_for_legacy_assessment_owner(env, signed):
    with env() as db:
        db.get(m.ClassRoom, 1).teacher_id = 4
        db.get(m.Assessment, 1).published = False
        db.commit()
    c = signed(2, 'teacher')
    assert c.post('/api/assessments/1/publish').status_code == 404
    signed(4, 'teacher')
    assert c.post('/api/assessments/1/publish').status_code == 404
    signed(3, 'admin')
    assert c.post('/api/assessments/1/publish').json() == {'id': 1, 'published': True, 'questions': 1}
    assert c.post('/api/assessments/999/publish').status_code == 404

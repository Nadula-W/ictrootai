"""Approved-question practice and transparent revision heuristics.

Only submitted answers reveal marking material. No student response is sent to an
LLM. PostgreSQL stores practice, idempotency and teacher-review history.
"""
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import case, func, literal, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession

from . import models as m
from .assessment_lifecycle import finalize_expired
from .database import get_db
from .security import current_user, staff
from .verification import mark

router = APIRouter(prefix='/api', tags=['practice'])
DIFFICULTIES = ('easy', 'medium', 'hard')


def student(user=Depends(current_user)):
    if user.role != 'student':
        raise HTTPException(403, 'Student access required')
    return user


class PracticeSubmission(BaseModel):
    value: str = Field(min_length=1, max_length=10000)
    request_id: UUID


class PracticeMark(BaseModel):
    score: float = Field(ge=0, le=1, allow_inf_nan=False)
    reason: str = Field(min_length=5, max_length=2000)

    @field_validator('reason')
    @classmethod
    def meaningful_reason(cls, value):
        if len(value.strip()) < 5:
            raise ValueError('Explain the marking decision')
        return value.strip()


def _utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def revision_summary(rows, now=None):
    """Summarise submitted evidence; a pending mark never counts as incorrect."""
    now = now or datetime.now(timezone.utc)
    grouped = defaultdict(list)
    for row in rows:
        grouped[row['outcome_id']].append(row)
    result = []
    for outcome_id, evidence in grouped.items():
        evidence.sort(key=lambda row: _utc(row['created']), reverse=True)
        marked = [row for row in evidence if row['score'] is not None]
        recent = marked[:5]
        accuracy = round(100 * sum(row['score'] for row in marked) / len(marked), 1) if marked else None
        recent_accuracy = round(100 * sum(row['score'] for row in recent) / len(recent), 1) if recent else None
        difficulty = 'easy' if recent_accuracy is None or recent_accuracy < 60 else ('medium' if recent_accuracy < 85 else 'hard')
        interval = 1 if recent_accuracy is None or recent_accuracy < 60 else (3 if recent_accuracy < 85 else 7)
        next_review = _utc(marked[0]['created']) + timedelta(days=interval) if marked else now
        misconceptions = Counter()
        for row in marked:
            if row['kind'] == 'mcq' and row['score'] == 0:
                label = next((option.get('misconception') for option in row['options'] if option.get('id') == row['value']), None)
                if isinstance(label, str) and label.strip():
                    misconceptions[label.strip()] += 1
        result.append({
            'outcome_id': outcome_id, 'text': evidence[0]['text'],
            'attempts': len(evidence), 'marked_attempts': len(marked),
            'pending': len(evidence) - len(marked), 'accuracy': accuracy,
            'recent_accuracy': recent_accuracy, 'recommended_difficulty': difficulty,
            'next_review_at': next_review.isoformat(), 'review_interval_days': interval,
            'due': next_review <= now,
            'status': 'Awaiting teacher review' if not marked else ('Needs practice' if recent_accuracy < 60 else ('Building confidence' if recent_accuracy < 85 else 'Confident')),
            'possible_misconceptions': [
                {'label': label, 'count': count, 'message': f'This pattern appeared in {count} responses. It is a possible misconception, not a diagnosis; review the explanations or ask your teacher.'}
                for label, count in sorted(misconceptions.items()) if count >= 2
            ],
        })
    return sorted(result, key=lambda row: (not row['due'], row['recent_accuracy'] if row['recent_accuracy'] is not None else -1, row['outcome_id']))


def _revision_rows(db, student_id, include_options=True):
    # Read only this student's evidence. Draft questions and unverified outcomes
    # cannot become recommendations, including through an old assessment. Do
    # not fetch answer-key, explanation or rubric JSON for a revision summary.
    common = [m.Question.id.label('question_id'), m.Outcome.id.label('outcome_id'), m.Outcome.text, m.Question.kind]
    if include_options:
        common.append(m.Question.options)
    practice = db.execute(select(*common, m.PracticeAnswer.score, m.PracticeAnswer.created, m.PracticeAnswer.value).select_from(m.PracticeAnswer).join(m.Question, m.Question.id == m.PracticeAnswer.question_id).join(m.Outcome, m.Outcome.id == m.Question.outcome_id).where(m.PracticeAnswer.student_id == student_id, m.Question.status == 'approved', m.Outcome.verified == True)).mappings()
    assessments = db.execute(select(*common, m.Answer.score, m.Attempt.started.label('created'), m.Answer.value).select_from(m.Answer).join(m.Attempt, m.Attempt.id == m.Answer.attempt_id).join(m.Question, m.Question.id == m.Answer.question_id).join(m.Outcome, m.Outcome.id == m.Question.outcome_id).where(m.Attempt.student_id == student_id, m.Attempt.submitted == True, m.Question.status == 'approved', m.Outcome.verified == True)).mappings()
    rows = [dict(row) for row in practice] + [dict(row) for row in assessments]
    if not include_options:
        for row in rows:
            row['options'] = []
    return rows


@router.get('/revision')
def revision(user=Depends(student), db: DBSession=Depends(get_db)):
    # The student dependency authorizes first. Do not sweep another learner's
    # attempts when their deadline passes while this learner opens revision.
    if finalize_expired(db, student_id=user.id):
        db.commit()
    return {
        'outcomes': revision_summary(_revision_rows(db, user.id)),
        'method': 'Difficulty uses the latest five marked responses: below 60% easy, 60–84% medium, 85% or above hard. Review intervals are 1, 3 or 7 days from the latest marked response. Pending marks are excluded. Assessment timing uses the recorded attempt start because a submission timestamp is not stored.',
        'message': 'Suggestions use your own submitted practice and assessment responses. Repeated distractor patterns are tentative and do not establish a diagnosis.',
    }


def _display_question(question, user, translations):
    result = {key: getattr(question, key) for key in ('id', 'outcome_id', 'kind', 'difficulty', 'prompt')}
    result['options'] = [{'id': option['id'], 'text': option['text']} for option in question.options]
    result['language'] = 'en'
    result['language_notice'] = None
    if user.language == 'si':
        translated = translations.get(question.id)
        content = translated.content if translated and isinstance(translated.content, dict) else {}
        prompt = content.get('prompt')
        options = content.get('options', [])
        valid_prompt = isinstance(prompt, str) and 5 <= len(prompt) <= 10000 and bool(prompt.strip())
        valid_options = isinstance(options, list) and len(options) == len(question.options) and all(
            isinstance(option, dict) and option.get('id') == original['id']
            and isinstance(option.get('text'), str) and 1 <= len(option['text']) <= 1000
            and bool(option['text'].strip())
            for option, original in zip(options, question.options)
        )
        if valid_prompt and valid_options:
            # Whitelist display fields even if an old translation contains other
            # JSON keys; require the approved option IDs and order as well.
            # Malformed legacy JSON must fall back rather than fail the request.
            result['prompt'] = prompt
            result['options'] = [{'id': option['id'], 'text': option['text']} for option in options]
            result['language'] = 'si'
        else:
            result['language_notice'] = 'Reviewed Sinhala translation unavailable or invalid. Showing original English.'
    return result


@router.get('/practice')
def practice_questions(outcome_id: str | None=None, difficulty: Literal['easy', 'medium', 'hard'] | None=None, limit: int=Query(default=5, ge=1, le=10), user=Depends(student), db: DBSession=Depends(get_db)):
    if finalize_expired(db, student_id=user.id):
        db.commit()
    statement = select(m.Question.id, m.Question.outcome_id, m.Question.kind, m.Question.difficulty, m.Question.prompt, m.Question.options).join(m.Outcome, m.Outcome.id == m.Question.outcome_id).where(m.Question.status == 'approved', m.Outcome.verified == True)
    if outcome_id:
        statement = statement.where(m.Question.outcome_id == outcome_id)
    if difficulty:
        statement = statement.where(m.Question.difficulty == difficulty)
    # Selection needs scores/timing, not distractor contents. Only the bounded
    # selected-question query below fetches candidate prompts and options JSON.
    evidence = _revision_rows(db, user.id, include_options=False)
    recommendations = {row['outcome_id']: row for row in revision_summary(evidence)}
    seen = Counter(row['question_id'] for row in evidence)

    def priority_case(values, column, default):
        # SQL CASE requires at least one WHEN. Literal defaults also keep a new
        # student's empty history valid without manufacturing a placeholder ID.
        return case(values, value=column, else_=default) if values else literal(default)

    due = {oid: int(not row['due']) for oid, row in recommendations.items()}
    accuracies = {oid: row['recent_accuracy'] if row['recent_accuracy'] is not None else -1 for oid, row in recommendations.items()}
    suggested = {oid: DIFFICULTIES.index(row['recommended_difficulty']) for oid, row in recommendations.items()}
    difficulty_rank = priority_case({name: index for index, name in enumerate(DIFFICULTIES)}, m.Question.difficulty, 0)
    statement = statement.order_by(
        priority_case(dict(seen), m.Question.id, 0),
        priority_case(due, m.Question.outcome_id, 0),
        priority_case(accuracies, m.Question.outcome_id, -1),
        func.abs(difficulty_rank - priority_case(suggested, m.Question.outcome_id, 0)),
        m.Question.id,
    ).limit(limit)
    questions = db.execute(statement).all()
    translations = {}
    if user.language == 'si' and questions:
        translations = {row.question_id: row for row in db.scalars(select(m.Translation).where(m.Translation.question_id.in_([question.id for question in questions]), m.Translation.language == 'si', m.Translation.reviewed == True))}
    return {'questions': [_display_question(question, user, translations) for question in questions], 'message': 'Approved questions from source-verified outcomes. Unseen questions and due revision are prioritised; answers are shown after you submit.' if questions else 'No approved practice questions match these filters yet. Ask your teacher to review questions for this topic.'}


def _feedback(answer, question):
    possible = None
    if answer.score == 0 and question.kind == 'mcq':
        possible = next((option.get('misconception') for option in question.options if option.get('id') == answer.value), None)
    return {
        'id': answer.id, 'question_id': question.id, 'outcome_id': question.outcome_id,
        'value': answer.value, 'score': answer.score, 'pending': answer.score is None,
        'reason': answer.reason, 'correct_answer': question.key,
        'explanation': question.explanation, 'rubric': question.rubric,
        'possible_misconception': possible,
        'misconception_notice': 'A single answer is insufficient to establish a misconception. This is a possible explanation to discuss with your teacher.' if possible else None,
        'created': _utc(answer.created).isoformat(),
    }


def _existing_submission(db, student_id, request_id, question_id, value):
    existing = db.scalar(select(m.PracticeAnswer).where(m.PracticeAnswer.student_id == student_id, m.PracticeAnswer.request_id == request_id))
    if existing:
        if existing.question_id != question_id or existing.value != value:
            raise HTTPException(409, 'This request ID was already used for a different response')
        return _feedback(existing, db.get(m.Question, question_id))
    return None


@router.post('/practice/{question_id}/submit')
def submit_practice(question_id: int, data: PracticeSubmission, user=Depends(student), db: DBSession=Depends(get_db)):
    request_id = str(data.request_id)
    existing = _existing_submission(db, user.id, request_id, question_id, data.value)
    if existing:
        return existing
    question = db.scalar(select(m.Question).join(m.Outcome, m.Outcome.id == m.Question.outcome_id).where(m.Question.id == question_id, m.Question.status == 'approved', m.Outcome.verified == True))
    if not question:
        raise HTTPException(404, 'Approved practice question not found')
    if question.kind == 'mcq' and data.value not in [option['id'] for option in question.options]:
        raise HTTPException(422, 'Select a valid option ID')
    score, reason = mark(question, data.value)
    answer = m.PracticeAnswer(student_id=user.id, question_id=question.id, value=data.value, score=score, reason=reason, request_id=request_id)
    db.add(answer)
    try:
        db.commit()
    except IntegrityError:
        # The unique student/request constraint serialises duplicate submissions
        # across workers. Re-read only after rolling back the failed transaction.
        db.rollback()
        existing = _existing_submission(db, user.id, request_id, question_id, data.value)
        if existing:
            return existing
        raise
    return _feedback(answer, question)


@router.post('/teacher/practice/{answer_id}/review')
def review_practice(answer_id: int, data: PracticeMark, user=Depends(staff), db: DBSession=Depends(get_db)):
    answer = db.scalar(select(m.PracticeAnswer).where(m.PracticeAnswer.id == answer_id).with_for_update())
    if not answer:
        raise HTTPException(404, 'Practice response not found')
    if user.role != 'admin':
        permitted = db.scalar(select(m.Membership.student_id).join(m.ClassRoom, m.ClassRoom.id == m.Membership.class_id).where(m.Membership.student_id == answer.student_id, m.ClassRoom.teacher_id == user.id).limit(1))
        if permitted is None:
            raise HTTPException(404, 'Practice response not found')
    answer.score = data.score
    answer.reason = data.reason
    answer.reviewed_by = user.id
    db.add(m.PracticeReview(answer_id=answer.id, teacher_id=user.id, score=data.score, reason=data.reason))
    db.commit()
    return {'id': answer.id, 'score': answer.score, 'pending': False, 'reason': answer.reason, 'reviewed_by': user.id}


@router.get('/teacher/practice')
def practice_review_queue(pending: bool=True, user=Depends(staff), db: DBSession=Depends(get_db)):
    statement = select(m.PracticeAnswer, m.Question, m.User).join(m.Question, m.Question.id == m.PracticeAnswer.question_id).join(m.User, m.User.id == m.PracticeAnswer.student_id)
    if user.role != 'admin':
        students = select(m.Membership.student_id).join(m.ClassRoom, m.ClassRoom.id == m.Membership.class_id).where(m.ClassRoom.teacher_id == user.id)
        statement = statement.where(m.PracticeAnswer.student_id.in_(students))
    if pending:
        statement = statement.where(m.PracticeAnswer.score.is_(None))
    return [{**_feedback(answer, question), 'student_id': learner.id, 'student': learner.name, 'prompt': question.prompt} for answer, question, learner in db.execute(statement.order_by(m.PracticeAnswer.created.desc()).limit(100))]

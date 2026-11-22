"""Approved-question planning and class-scoped teacher learning reports.

Planning is read-only. These are practice-paper labels, not an official exam
blueprint. Reports use submitted answers only and never turn a distractor label
into a diagnosis of a student.
"""
from collections import Counter, defaultdict, deque
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session as DBSession

from . import models as m
from .assessment_lifecycle import finalize_expired
from .database import get_db
from .security import staff


router = APIRouter(prefix='/api', tags=['Assessment planning and class progress'])
QuestionKind = Literal['mcq', 'number', 'boolean', 'output', 'sql', 'short', 'structured']
Difficulty = Literal['easy', 'medium', 'hard']
OutcomeId = Annotated[str, Field(min_length=1, max_length=120)]
UnitId = Annotated[int, Field(ge=1, le=14)]
PRACTICE_NOTICE = 'Practice selection only; this is not an official examination blueprint.'
MISCONCEPTION_NOTICE = (
    'Repeated answers suggest a possible area to discuss with the student; '
    'this is tentative evidence, not a diagnosis.'
)


class AssessmentPreview(BaseModel):
    model_config = ConfigDict(extra='forbid')

    outcome_ids: list[OutcomeId] = Field(default_factory=list, max_length=100)
    unit_ids: list[UnitId] = Field(default_factory=list, max_length=14)
    difficulty: Difficulty | None = None
    kinds: list[QuestionKind] = Field(default_factory=list, max_length=7)
    count: int = Field(default=10, ge=1, le=100)
    style: Literal['custom', 'paper_i', 'paper_ii'] = 'custom'

    @model_validator(mode='after')
    def compatible_filters(self):
        for name in ('outcome_ids', 'unit_ids', 'kinds'):
            values = getattr(self, name)
            if len(values) != len(set(values)):
                raise ValueError(f'{name} must not contain duplicates')
        permitted = {'paper_i': {'mcq'}, 'paper_ii': {'short', 'structured'}}.get(self.style)
        if permitted is not None and self.kinds and not set(self.kinds).issubset(permitted):
            raise ValueError('Question formats conflict with the selected practice-paper style')
        return self


@router.post('/assessments/preview')
def preview_assessment(data: AssessmentPreview, user=Depends(staff), db: DBSession = Depends(get_db)):
    outcome_query = select(m.Outcome.id, m.Outcome.text, m.Outcome.unit_id).where(m.Outcome.verified.is_(True))
    if data.outcome_ids:
        outcome_query = outcome_query.where(m.Outcome.id.in_(data.outcome_ids))
    if data.unit_ids:
        outcome_query = outcome_query.where(m.Outcome.unit_id.in_(data.unit_ids))
    outcomes = db.execute(outcome_query.order_by(m.Outcome.unit_id, m.Outcome.id)).all()
    by_id = {o.id: o for o in outcomes}
    if data.outcome_ids:
        invalid = [oid for oid in data.outcome_ids if oid not in by_id]
        if invalid:
            raise HTTPException(422, detail={
                'message': 'Every requested outcome must exist, be source-verified and match the selected units.',
                'unavailable_outcome_ids': invalid,
            })
        ordered_ids = data.outcome_ids
    else:
        ordered_ids = [o.id for o in outcomes]

    kinds = data.kinds or {'paper_i': ['mcq'], 'paper_ii': ['short', 'structured']}.get(data.style, [])
    conditions = [m.Question.status == 'approved', m.Question.outcome_id.in_(ordered_ids)]
    if data.difficulty:
        conditions.append(m.Question.difficulty == data.difficulty)
    if kinds:
        conditions.append(m.Question.kind.in_(kinds))
    available_counts = dict(db.execute(select(m.Question.outcome_id, func.count()).where(
        *conditions
    ).group_by(m.Question.outcome_id)).all())
    available = sum(available_counts.values())
    if available < data.count:
        raise HTTPException(422, detail={
            'message': f'Only {available} approved questions match; {data.count} requested. Add approved questions or reduce the count.',
            'requested_count': data.count,
            'available_count': available,
            'shortage': data.count - available,
        })

    # Allocate at most count slots before fetching prompts, so a large approved
    # bank cannot turn a bounded preview into an unbounded metadata download.
    remaining = available_counts.copy()
    candidates = deque(oid for oid in ordered_ids if remaining.get(oid))
    selection_order = []
    selected_counts = Counter()
    while candidates and len(selection_order) < data.count:
        oid = candidates.popleft()
        selection_order.append(oid)
        selected_counts[oid] += 1
        remaining[oid] -= 1
        if remaining[oid]:
            candidates.append(oid)
    ranked = select(
        m.Question.id, m.Question.outcome_id, m.Question.kind, m.Question.difficulty, m.Question.prompt,
        func.row_number().over(partition_by=m.Question.outcome_id, order_by=m.Question.id).label('position'),
    ).where(*conditions, m.Question.outcome_id.in_(selected_counts)).subquery()
    questions = db.execute(select(
        ranked.c.id, ranked.c.outcome_id, ranked.c.kind, ranked.c.difficulty, ranked.c.prompt,
    ).where(ranked.c.position <= case(dict(selected_counts), value=ranked.c.outcome_id, else_=0)).order_by(ranked.c.id)).all()
    grouped = defaultdict(deque)
    for question in questions:
        grouped[question.outcome_id].append(question)
    selected = [grouped[oid].popleft() for oid in selection_order]
    represented = [oid for oid in ordered_ids if selected_counts[oid]]
    return {
        'question_ids': [q.id for q in selected],
        'questions': [{
            'id': q.id, 'outcome_id': q.outcome_id, 'outcome': by_id[q.outcome_id].text,
            'unit_id': by_id[q.outcome_id].unit_id, 'kind': q.kind,
            'difficulty': q.difficulty, 'prompt': q.prompt,
        } for q in selected],
        'requested_count': data.count, 'available_count': available, 'count': len(selected),
        'shortage': 0, 'style': data.style, 'practice_notice': PRACTICE_NOTICE,
        'coverage': {
            'requested_outcome_count': len(ordered_ids),
            'represented_outcome_count': len(represented),
            'outcome_ids': represented,
            'per_outcome': [{
                'outcome_id': oid, 'available': available_counts.get(oid, 0), 'selected': selected_counts[oid],
            } for oid in ordered_ids],
        },
    }


def _owned_class(db, class_id, user):
    query = select(m.ClassRoom).where(m.ClassRoom.id == class_id)
    if user.role != 'admin':
        query = query.where(m.ClassRoom.teacher_id == user.id)
    classroom = db.scalar(query)
    if classroom is None:
        raise HTTPException(404, 'Class not found')
    return classroom


def _accuracy(total, marked):
    return round(100 * float(total) / marked) if marked else None


def _recommended_difficulty(scores):
    if not scores:
        return 'medium'
    recent = scores[-5:]
    average = sum(recent) / len(recent)
    if average < 0.5:
        return 'easy'
    return 'hard' if len(scores) >= 3 and average >= 0.8 else 'medium'


@router.get('/classes/{class_id}/students')
def class_students(class_id: int, user=Depends(staff), db: DBSession = Depends(get_db)):
    classroom = _owned_class(db, class_id, user)
    if finalize_expired(db, class_ids=[class_id]):
        db.commit()
    attempt_stats = select(
        m.Attempt.student_id.label('student_id'),
        func.count(m.Attempt.id).label('started_assessments'),
        func.count(m.Attempt.id).filter(m.Attempt.submitted.is_(True)).label('submitted_assessments'),
        func.max(m.Attempt.started).filter(m.Attempt.submitted.is_(True)).label('latest_submitted_attempt_started'),
    ).select_from(m.Attempt).join(m.Assessment, m.Assessment.id == m.Attempt.assessment_id).where(
        m.Assessment.class_id == class_id
    ).group_by(m.Attempt.student_id).subquery()
    answer_stats = select(
        m.Attempt.student_id.label('student_id'),
        func.count(m.Answer.score).label('marked_answers'),
        func.sum(m.Answer.score).label('score'),
        func.count(m.Answer.question_id).filter(m.Answer.score.is_(None)).label('pending_answers'),
    ).select_from(m.Attempt).join(m.Answer, m.Answer.attempt_id == m.Attempt.id).join(
        m.Assessment, m.Assessment.id == m.Attempt.assessment_id
    ).where(m.Assessment.class_id == class_id, m.Attempt.submitted.is_(True)).group_by(m.Attempt.student_id).subquery()
    rows = db.execute(select(
        m.User.id, m.User.name, m.User.email, m.User.grade,
        attempt_stats.c.started_assessments, attempt_stats.c.submitted_assessments,
        attempt_stats.c.latest_submitted_attempt_started,
        answer_stats.c.marked_answers, answer_stats.c.score, answer_stats.c.pending_answers,
    ).select_from(m.User).join(m.Membership, m.Membership.student_id == m.User.id).outerjoin(
        attempt_stats, attempt_stats.c.student_id == m.User.id
    ).outerjoin(answer_stats, answer_stats.c.student_id == m.User.id).where(
        m.Membership.class_id == class_id, m.User.role == 'student'
    ).order_by(m.User.name, m.User.id)).all()
    return {
        'class_id': classroom.id, 'class_name': classroom.name,
        'students': [{
            'id': row.id, 'name': row.name, 'email': row.email, 'grade': row.grade,
            'started_assessments': row.started_assessments or 0,
            'submitted_assessments': row.submitted_assessments or 0,
            'marked_answers': row.marked_answers or 0, 'pending_answers': row.pending_answers or 0,
            'accuracy': _accuracy(row.score or 0, row.marked_answers or 0),
            'latest_submitted_attempt_started': row.latest_submitted_attempt_started.isoformat() if row.latest_submitted_attempt_started else None,
        } for row in rows],
        'accuracy_notice': 'Accuracy includes marked answers from submitted assessments in this class only; pending teacher marks are excluded.',
    }


@router.get('/classes/{class_id}/students/{student_id}/progress')
def student_class_progress(class_id: int, student_id: int, user=Depends(staff), db: DBSession = Depends(get_db)):
    classroom = _owned_class(db, class_id, user)
    student = db.scalar(select(m.User).join(m.Membership, m.Membership.student_id == m.User.id).where(
        m.Membership.class_id == class_id, m.User.id == student_id, m.User.role == 'student'
    ))
    if student is None:
        raise HTTPException(404, 'Student not found in this class')
    if finalize_expired(db, class_ids=[class_id], student_id=student_id):
        db.commit()
    rows = db.execute(select(
        m.Attempt.id.label('attempt_id'), m.Attempt.started,
        m.Answer.question_id, m.Answer.score, m.Answer.value,
        m.Question.kind, m.Question.options, m.Question.outcome_id, m.Outcome.text.label('outcome_text'),
    ).select_from(m.Attempt).join(m.Assessment, m.Assessment.id == m.Attempt.assessment_id).outerjoin(
        m.Answer, m.Answer.attempt_id == m.Attempt.id
    ).outerjoin(m.Question, m.Question.id == m.Answer.question_id).outerjoin(
        m.Outcome, m.Outcome.id == m.Question.outcome_id
    ).where(
        m.Assessment.class_id == class_id, m.Attempt.student_id == student_id, m.Attempt.submitted.is_(True)
    ).order_by(m.Attempt.started, m.Attempt.id, m.Answer.question_id)).all()
    topics = {}
    misconception_events = defaultdict(list)
    all_scores = []
    pending = 0
    attempts = {row.attempt_id for row in rows}
    for row in rows:
        if row.question_id is None:
            continue
        topic = topics.setdefault(row.outcome_id, {
            'outcome_id': row.outcome_id, 'text': row.outcome_text,
            'scores': [], 'pending_answers': 0,
        })
        if row.score is None:
            topic['pending_answers'] += 1
            pending += 1
            continue
        topic['scores'].append(row.score)
        all_scores.append(row.score)
        if row.kind == 'mcq' and row.score == 0:
            label = next((option.get('misconception') for option in row.options if option.get('id') == row.value), None)
            if isinstance(label, str) and label.strip():
                misconception_events[(row.outcome_id, label.strip())].append((row.attempt_id, row.question_id))
    outcomes = []
    for topic in topics.values():
        scores = topic.pop('scores')
        outcomes.append({
            **topic, 'answered': len(scores), 'accuracy': _accuracy(sum(scores), len(scores)),
            'recommended_difficulty': _recommended_difficulty(scores),
            'evidence_notice': 'Limited marked-answer evidence.' if len(scores) < 3 else None,
        })
    possible = [{
        'outcome_id': oid, 'label': label, 'evidence_count': len(events),
        'question_count': len({qid for _, qid in events}), 'notice': MISCONCEPTION_NOTICE,
    } for (oid, label), events in sorted(misconception_events.items()) if len(events) >= 2]
    weak = [topic for topic in outcomes if topic['accuracy'] is not None and topic['accuracy'] < 60]
    weak.sort(key=lambda topic: (topic['accuracy'], topic['outcome_id']))
    return {
        'class_id': classroom.id, 'class_name': classroom.name,
        'student': {'id': student.id, 'name': student.name, 'email': student.email, 'grade': student.grade},
        'submitted_assessments': len(attempts), 'marked_answers': len(all_scores), 'pending_answers': pending,
        'accuracy': _accuracy(sum(all_scores), len(all_scores)),
        'recommended_difficulty': _recommended_difficulty(all_scores),
        'outcomes': outcomes, 'weak_outcomes': weak, 'possible_misconceptions': possible,
        'accuracy_notice': 'Submitted assessments in this class only; pending teacher marks are excluded from accuracy.',
        'misconception_notice': MISCONCEPTION_NOTICE,
    }

"""Transactional finalization of saved answers after an assessment deadline.

Every call must have an explicit student/assessment/class/attempt/teacher scope
that its caller has already authorized. There is no global or startup sweep.
Callers own commit/rollback; locks and marking remain in the same transaction.
"""
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import literal, select

from . import models as m
from .verification import mark


def as_utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def attempt_deadline(started, duration):
    return as_utc(started) + timedelta(minutes=duration)


def grade_saved_answers(db, attempts):
    """Mark a caller-locked batch, including blanks, without committing it.

    Manual submission takes its conditional guard before calling this helper;
    deadline finalization locks only unsubmitted expired attempts. Answer writes
    take that same attempt lock, so no late save can race the snapshot being
    marked. No AI or student code execution is involved.
    """
    attempts = list(attempts)
    if not attempts:
        return []
    attempt_ids = [attempt.id for attempt in attempts]
    assessment_ids = {attempt.assessment_id for attempt in attempts}
    questions = defaultdict(list)
    for assessment_id, question in db.execute(select(m.AssessmentQuestion.assessment_id, m.Question).join(
        m.Question, m.Question.id == m.AssessmentQuestion.question_id
    ).where(m.AssessmentQuestion.assessment_id.in_(assessment_ids)).order_by(
        m.AssessmentQuestion.assessment_id, m.AssessmentQuestion.position, m.Question.id
    )):
        questions[assessment_id].append(question)
    answers = {(answer.attempt_id, answer.question_id): answer for answer in db.scalars(
        select(m.Answer).where(m.Answer.attempt_id.in_(attempt_ids))
    )}
    for attempt in attempts:
        for question in questions[attempt.assessment_id]:
            answer = answers.get((attempt.id, question.id))
            if answer is None:
                answer = m.Answer(attempt_id=attempt.id, question_id=question.id, value='')
                db.add(answer)
            answer.score, answer.reason = mark(question, answer.value) if answer.value else (0.0, 'No answer submitted')
            # A descriptive answer remains pending. Confidence is not a mark.
            answer.reviewed_by = None
        attempt.submitted = True
    db.flush()
    return attempt_ids


def finalize_expired(db, *, student_id=None, assessment_ids=None, class_ids=None,
                     attempt_ids=None, teacher_id=None, now=None):
    """Finalize expired, explicitly scoped attempts; return changed IDs.

    An empty explicit ID list selects nothing. All supplied scopes intersect.
    Unscoped use is rejected before SQL; caller authorization must happen before
    calling (especially for a direct attempt/class ID supplied in an HTTP path).
    Expiry is inclusive: now >= started + duration, with UTC-aware timestamps.
    """
    if all(value is None for value in (student_id, assessment_ids, class_ids, attempt_ids, teacher_id)):
        raise ValueError('Deadline finalization requires an authorized scope')
    query = select(m.Attempt).join(m.Assessment, m.Assessment.id == m.Attempt.assessment_id).where(
        m.Attempt.submitted.is_(False)
    )
    for column, values in ((m.Assessment.id, assessment_ids), (m.Assessment.class_id, class_ids), (m.Attempt.id, attempt_ids)):
        if values is not None:
            values = tuple(set(values))
            if not values:
                return []
            if any(isinstance(value, bool) or not isinstance(value, int) or value < 1 for value in values):
                raise ValueError('Invalid deadline-finalization scope')
            query = query.where(column.in_(values))
    for column, value in ((m.Attempt.student_id, student_id), (m.Assessment.teacher_id, teacher_id)):
        if value is not None:
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError('Invalid deadline-finalization scope')
            query = query.where(column == value)
    moment = as_utc(now or datetime.now(timezone.utc))
    query = query.where(
        m.Attempt.started + m.Assessment.duration * literal(timedelta(minutes=1)) <= moment
    ).order_by(m.Attempt.id).with_for_update(of=m.Attempt)
    attempts = db.scalars(query).all()
    return grade_saved_answers(db, attempts)

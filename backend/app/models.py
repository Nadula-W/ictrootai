from datetime import datetime, timezone
from sqlalchemy import String, Text, ForeignKey, UniqueConstraint, JSON, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base

def now():
    return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    password: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(20), default='student')
    grade: Mapped[int] = mapped_column(default=12)
    language: Mapped[str] = mapped_column(default='en')

class Session(Base):
    __tablename__ = 'sessions'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    expires: Mapped[datetime] = mapped_column(DateTime(timezone=True))

class CurriculumVersion(Base):
    __tablename__ = 'curriculum_versions'
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    source: Mapped[str] = mapped_column(Text)
    applicability: Mapped[str] = mapped_column(Text)
    verified_complete: Mapped[bool] = mapped_column(default=False)

class Unit(Base):
    __tablename__ = 'units'
    id: Mapped[int] = mapped_column(primary_key=True)
    version_id: Mapped[str] = mapped_column(ForeignKey('curriculum_versions.id'))
    name: Mapped[str] = mapped_column(String(200))
    grade: Mapped[int | None]
    verified: Mapped[bool] = mapped_column(default=False)

class Outcome(Base):
    __tablename__ = 'learning_outcomes'
    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey('units.id'), index=True)
    subtopic: Mapped[str] = mapped_column(Text)
    competency: Mapped[str] = mapped_column(Text, default='')
    level: Mapped[str] = mapped_column(String(30))
    text: Mapped[str] = mapped_column(Text)
    source_page: Mapped[int]
    verified: Mapped[bool] = mapped_column(default=False)
    reviewed_at: Mapped[str | None] = mapped_column(nullable=True)

class Resource(Base):
    __tablename__ = 'learning_resources'
    id: Mapped[int] = mapped_column(primary_key=True)
    outcome_id: Mapped[str] = mapped_column(ForeignKey('learning_outcomes.id'), index=True)
    title: Mapped[str] = mapped_column(String(200))
    source: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    reviewed: Mapped[bool] = mapped_column(default=False)
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(nullable=True)

class Question(Base):
    __tablename__ = 'questions'
    id: Mapped[int] = mapped_column(primary_key=True)
    outcome_id: Mapped[str] = mapped_column(ForeignKey('learning_outcomes.id'), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    difficulty: Mapped[str] = mapped_column(String(20))
    prompt: Mapped[str] = mapped_column(Text)
    options: Mapped[list] = mapped_column(JSON, default=list)
    key: Mapped[dict] = mapped_column(JSON)
    explanation: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(default='draft', index=True)
    sources: Mapped[list] = mapped_column(JSON, default=list)
    author_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    rubric: Mapped[list] = mapped_column(JSON, default=list)

class Translation(Base):
    __tablename__ = 'translations'
    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey('questions.id'))
    language: Mapped[str] = mapped_column(default='si')
    content: Mapped[dict] = mapped_column(JSON)
    reviewed: Mapped[bool] = mapped_column(default=False)
    __table_args__ = (UniqueConstraint('question_id', 'language'),)

class Validation(Base):
    __tablename__ = 'question_validations'
    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey('questions.id'))
    reviewer_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    decision: Mapped[str]
    reason: Mapped[str] = mapped_column(Text)
    created: Mapped[datetime] = mapped_column(default=now)

class ClassRoom(Base):
    __tablename__ = 'classes'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    teacher_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    grade: Mapped[int]
    code: Mapped[str] = mapped_column(unique=True)

class Membership(Base):
    __tablename__ = 'class_memberships'
    class_id: Mapped[int] = mapped_column(ForeignKey('classes.id'), primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey('users.id'), primary_key=True)

class Assessment(Base):
    __tablename__ = 'assessments'
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str]
    teacher_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    class_id: Mapped[int] = mapped_column(ForeignKey('classes.id'))
    duration: Mapped[int]
    published: Mapped[bool] = mapped_column(default=False)

class AssessmentQuestion(Base):
    __tablename__ = 'assessment_questions'
    assessment_id: Mapped[int] = mapped_column(ForeignKey('assessments.id'), primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey('questions.id'), primary_key=True)
    position: Mapped[int]

class Attempt(Base):
    __tablename__ = 'student_attempts'
    id: Mapped[int] = mapped_column(primary_key=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey('assessments.id'))
    student_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    started: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    submitted: Mapped[bool] = mapped_column(default=False)
    __table_args__ = (UniqueConstraint('assessment_id', 'student_id'),)

class Answer(Base):
    __tablename__ = 'student_answers'
    attempt_id: Mapped[int] = mapped_column(ForeignKey('student_attempts.id'), primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey('questions.id'), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    score: Mapped[float | None] = mapped_column(nullable=True)
    reason: Mapped[str] = mapped_column(Text, default='Awaiting submission')
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)

class TeacherReview(Base):
    __tablename__ = 'teacher_reviews'
    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey('student_attempts.id'))
    question_id: Mapped[int] = mapped_column(ForeignKey('questions.id'))
    teacher_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    score: Mapped[float]
    reason: Mapped[str] = mapped_column(Text)

class GenerationLog(Base):
    __tablename__ = 'ai_generation_logs'
    id: Mapped[int] = mapped_column(primary_key=True)
    model: Mapped[str]
    outcome_id: Mapped[str]
    status: Mapped[str]
    created: Mapped[datetime] = mapped_column(default=now)

class AppSetting(Base):
    __tablename__ = 'app_settings'
    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[str]

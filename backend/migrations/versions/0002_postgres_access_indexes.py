"""PostgreSQL access restrictions and foreign-key lookup indexes."""
from alembic import op
import sqlalchemy as sa

revision='0002'
down_revision='0001'

INDEXES=[
    ('sessions','user_id'),('units','version_id'),('questions','author_id'),
    ('question_validations','question_id'),('question_validations','reviewer_id'),
    ('classes','teacher_id'),('class_memberships','student_id'),
    ('assessments','teacher_id'),('assessments','class_id'),
    ('assessment_questions','question_id'),('student_attempts','student_id'),
    ('student_answers','question_id'),('student_answers','reviewed_by'),
    ('teacher_reviews','attempt_id'),('teacher_reviews','question_id'),('teacher_reviews','teacher_id'),
]
TABLES=['ai_generation_logs','app_settings','curriculum_versions','users','classes','sessions','units','assessments','class_memberships','learning_outcomes','learning_resources','questions','student_attempts','assessment_questions','question_validations','student_answers','teacher_reviews','translations','alembic_version']

def upgrade():
    for table,column in INDEXES:op.create_index(f'ix_{table}_{column}',table,[column])
    for table in TABLES:
        op.execute(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'REVOKE ALL ON TABLE public."{table}" FROM PUBLIC, anon, authenticated')
    op.execute('REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC, anon, authenticated')

def downgrade():
    for table,column in reversed(INDEXES):op.drop_index(f'ix_{table}_{column}',table_name=table)
    # Keep access restrictions during rollback; do not reopen protected data.

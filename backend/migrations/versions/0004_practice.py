"""Persistent practice, idempotent submissions and teacher marking audit."""
from alembic import op
import sqlalchemy as sa

revision = '0004'
down_revision = '0003'


def upgrade():
    op.create_table('practice_answers',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('question_id', sa.Integer(), sa.ForeignKey('questions.id'), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('score', sa.Float(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('created', sa.DateTime(timezone=True), nullable=False),
        sa.Column('request_id', sa.String(64), nullable=False),
        sa.Column('reviewed_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.UniqueConstraint('student_id', 'request_id', name='uq_practice_answers_student_request'),
    )
    op.create_table('practice_reviews',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('answer_id', sa.Integer(), sa.ForeignKey('practice_answers.id'), nullable=False),
        sa.Column('teacher_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('created', sa.DateTime(timezone=True), nullable=False),
    )
    for table, column in [('practice_answers', 'student_id'), ('practice_answers', 'question_id'), ('practice_answers', 'reviewed_by'), ('practice_reviews', 'answer_id'), ('practice_reviews', 'teacher_id')]:
        op.create_index(f'ix_{table}_{column}', table, [column])
    for table in ('practice_answers', 'practice_reviews'):
        op.execute(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'REVOKE ALL ON TABLE public."{table}" FROM PUBLIC')
        op.execute(f'REVOKE ALL ON SEQUENCE public."{table}_id_seq" FROM PUBLIC')
        for role in ('anon', 'authenticated'):
            op.execute(f'''DO $$ BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                    REVOKE ALL ON TABLE public."{table}" FROM "{role}";
                    REVOKE ALL ON SEQUENCE public."{table}_id_seq" FROM "{role}";
                END IF;
            END $$''')


def downgrade():
    op.drop_table('practice_reviews')
    op.drop_table('practice_answers')

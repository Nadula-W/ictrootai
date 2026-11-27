"""Teacher applications require administrator approval; existing roles preserved."""
from alembic import op
import sqlalchemy as sa
revision='0005'
down_revision='0004'
def upgrade():
    op.create_table('teacher_applications',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('user_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=False,unique=True),sa.Column('status',sa.String(20),nullable=False),sa.Column('message',sa.Text(),nullable=False),sa.Column('reason',sa.Text(),nullable=False),sa.Column('reviewer_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=True),sa.Column('created',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_teacher_applications_reviewer_id','teacher_applications',['reviewer_id'])
    op.execute('ALTER TABLE teacher_applications ENABLE ROW LEVEL SECURITY')
    op.execute('REVOKE ALL ON TABLE teacher_applications FROM PUBLIC')
    op.execute('REVOKE ALL ON SEQUENCE teacher_applications_id_seq FROM PUBLIC')
    for role in ('anon','authenticated'):
        op.execute(f"DO $$ BEGIN IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='{role}') THEN REVOKE ALL ON TABLE teacher_applications FROM {role}; REVOKE ALL ON SEQUENCE teacher_applications_id_seq FROM {role}; END IF; END $$")
def downgrade():op.drop_table('teacher_applications')

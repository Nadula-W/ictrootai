"""Preserve source-audited competency levels and outcome provenance.

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa

revision='0003'
down_revision='0002'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('competency_levels',
        sa.Column('id',sa.String(150),primary_key=True),
        sa.Column('unit_id',sa.Integer(),sa.ForeignKey('units.id'),nullable=False),
        sa.Column('level',sa.String(30),nullable=False),
        sa.Column('title',sa.Text(),nullable=False),
        sa.Column('source_pages',sa.JSON(),nullable=False),
        sa.Column('contents',sa.JSON(),nullable=False),
        sa.Column('periods',sa.Integer(),nullable=True),
        sa.Column('review_note',sa.Text(),nullable=False),
        sa.UniqueConstraint('unit_id','level'))
    op.create_index('ix_competency_levels_unit_id','competency_levels',['unit_id'])
    op.add_column('learning_outcomes',sa.Column('source_pages',sa.JSON(),nullable=False,server_default=sa.text("'[]'")))
    op.add_column('learning_outcomes',sa.Column('review_note',sa.Text(),nullable=False,server_default=''))
    op.add_column('learning_outcomes',sa.Column('catalogued',sa.Boolean(),nullable=False,server_default=sa.false()))
    if op.get_bind().dialect.name=='postgresql':
        op.execute('ALTER TABLE competency_levels ENABLE ROW LEVEL SECURITY')
        op.execute('REVOKE ALL ON TABLE competency_levels FROM PUBLIC')
        op.execute("DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON TABLE competency_levels FROM anon; END IF; IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON TABLE competency_levels FROM authenticated; END IF; END $$")

def downgrade():
    op.drop_column('learning_outcomes','catalogued')
    op.drop_column('learning_outcomes','review_note')
    op.drop_column('learning_outcomes','source_pages')
    op.drop_index('ix_competency_levels_unit_id',table_name='competency_levels')
    op.drop_table('competency_levels')

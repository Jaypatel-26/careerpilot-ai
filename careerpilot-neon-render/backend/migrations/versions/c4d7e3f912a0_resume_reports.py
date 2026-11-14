"""Create account-owned resume analysis reports; keep existing data intact.

Revision ID: c4d7e3f912a0
Revises: b7c8d9e402f1
"""
from alembic import op
import sqlalchemy as sa

revision = 'c4d7e3f912a0'
down_revision = 'b7c8d9e402f1'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('resume_reports',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('request_id', sa.Uuid(), nullable=False),
        sa.Column('input_hash', sa.String(64), nullable=False),
        sa.Column('report', sa.JSON(), nullable=False),
        sa.Column('model_name', sa.String(100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('user_id','request_id',name='uq_resume_report_user_request'))
    op.create_index('ix_resume_reports_user_id', 'resume_reports', ['user_id'])
    if op.get_bind().dialect.name == 'postgresql':
        op.execute('ALTER TABLE resume_reports ENABLE ROW LEVEL SECURITY')

def downgrade():
    # This removes saved resume reports; back up before rolling back.
    op.drop_index('ix_resume_reports_user_id', table_name='resume_reports')
    op.drop_table('resume_reports')

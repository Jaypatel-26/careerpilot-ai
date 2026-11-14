"""Add account-owned saved jobs and job-match history.

Revision ID: d6a3b8f710e2
Revises: c4d7e3f912a0
"""
from alembic import op
import sqlalchemy as sa
revision='d6a3b8f710e2'
down_revision='c4d7e3f912a0'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('saved_jobs',
      sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('user_id',sa.Uuid(),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),
      sa.Column('job_key',sa.String(120),nullable=False),sa.Column('job',sa.JSON(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
      sa.UniqueConstraint('user_id','job_key',name='uq_saved_job_user_key'))
    op.create_index('ix_saved_jobs_user_id','saved_jobs',['user_id'])
    op.create_table('job_match_reports',
      sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('user_id',sa.Uuid(),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),
      sa.Column('resume_report_id',sa.Uuid(),sa.ForeignKey('resume_reports.id',ondelete='SET NULL'),nullable=True),
      sa.Column('request_id',sa.Uuid(),nullable=False),sa.Column('input_hash',sa.String(64),nullable=False),sa.Column('job_key',sa.String(120),nullable=False),
      sa.Column('job',sa.JSON(),nullable=False),sa.Column('report',sa.JSON(),nullable=False),sa.Column('model_name',sa.String(100),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
      sa.UniqueConstraint('user_id','request_id',name='uq_job_match_user_request'))
    op.create_index('ix_job_match_reports_user_id','job_match_reports',['user_id'])
    if op.get_bind().dialect.name=='postgresql':
        op.execute('ALTER TABLE saved_jobs ENABLE ROW LEVEL SECURITY')
        op.execute('ALTER TABLE job_match_reports ENABLE ROW LEVEL SECURITY')

def downgrade():
    # Irreversible loss of saved jobs/matches. Back up first.
    op.drop_index('ix_job_match_reports_user_id',table_name='job_match_reports');op.drop_table('job_match_reports')
    op.drop_index('ix_saved_jobs_user_id',table_name='saved_jobs');op.drop_table('saved_jobs')

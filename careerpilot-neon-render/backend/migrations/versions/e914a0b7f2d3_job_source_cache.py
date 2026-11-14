"""Short-lived Adzuna search snapshots. No existing user tables are modified.

Revision ID: e914a0b7f2d3
Revises: d6a3b8f710e2
"""
from alembic import op
import sqlalchemy as sa
revision='e914a0b7f2d3'
down_revision='d6a3b8f710e2'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('job_source_cache',sa.Column('job_key',sa.String(120),primary_key=True),sa.Column('job',sa.JSON(),nullable=False),sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_job_source_cache_expires_at','job_source_cache',['expires_at'])
    if op.get_bind().dialect.name=='postgresql':op.execute('ALTER TABLE job_source_cache ENABLE ROW LEVEL SECURITY')

def downgrade():
    op.drop_index('ix_job_source_cache_expires_at',table_name='job_source_cache');op.drop_table('job_source_cache')

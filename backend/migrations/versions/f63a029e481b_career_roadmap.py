"""Add account-owned career plans without changing existing data.
Revision ID: f63a029e481b
Revises: e914a0b7f2d3
"""
from alembic import op
import sqlalchemy as sa
revision='f63a029e481b'
down_revision='e914a0b7f2d3'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('career_plans',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('user_id',sa.Uuid(),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),sa.Column('goal',sa.JSON(),nullable=False),sa.Column('roadmap',sa.JSON(),nullable=True),sa.Column('request_id',sa.Uuid()),sa.Column('input_hash',sa.String(64)),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_career_plans_user_id','career_plans',['user_id'],unique=True)
    if op.get_bind().dialect.name=='postgresql':op.execute('ALTER TABLE career_plans ENABLE ROW LEVEL SECURITY')

def downgrade():
    op.drop_index('ix_career_plans_user_id',table_name='career_plans')
    op.drop_table('career_plans')

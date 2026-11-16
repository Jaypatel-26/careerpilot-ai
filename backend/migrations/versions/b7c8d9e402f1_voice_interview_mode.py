"""Distinguish voice interviews from existing text sessions without deleting data.

Revision ID: b7c8d9e402f1
Revises: 9f0a2c7d842e
"""
from alembic import op
import sqlalchemy as sa

revision = 'b7c8d9e402f1'
down_revision = '9f0a2c7d842e'
branch_labels = None
depends_on = None


def upgrade():
    # Existing records receive text mode and remain accessible in history.
    op.add_column('interview_sessions', sa.Column('mode', sa.String(10), nullable=False, server_default='text'))


def downgrade():
    # The column's mode distinction will be lost; existing records are not removed.
    op.drop_column('interview_sessions', 'mode')

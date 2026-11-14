"""Add account-owned career profile fields without modifying existing data.

Revision ID: 6e7c2a9d3011
Revises: 4d2e9a1b8c10
"""
from alembic import op
import sqlalchemy as sa

revision = '6e7c2a9d3011'
down_revision = '4d2e9a1b8c10'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('target_role', sa.String(150), nullable=True))
    op.add_column('users', sa.Column('experience_level', sa.String(20), nullable=True))
    op.add_column('users', sa.Column('skills', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('career_goals', sa.Text(), nullable=True))


def downgrade():
    # Downgrade removes saved career details; take a backup before rolling back.
    op.drop_column('users', 'career_goals')
    op.drop_column('users', 'skills')
    op.drop_column('users', 'experience_level')
    op.drop_column('users', 'target_role')

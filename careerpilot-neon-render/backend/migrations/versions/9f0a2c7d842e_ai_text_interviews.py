"""Add optional AI setup context and structured report; retain existing data.

Revision ID: 9f0a2c7d842e
Revises: 6e7c2a9d3011
"""
from alembic import op
import sqlalchemy as sa

revision = '9f0a2c7d842e'
down_revision = '6e7c2a9d3011'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('interview_sessions', sa.Column('question_focus', sa.String(20), nullable=True))
    op.add_column('interview_sessions', sa.Column('experience_level', sa.String(20), nullable=True))
    op.add_column('interview_sessions', sa.Column('skills', sa.Text(), nullable=True))
    op.add_column('interview_reports', sa.Column('details', sa.JSON(), nullable=True))


def downgrade():
    # Removing these columns loses AI context and structured report content.
    op.drop_column('interview_reports', 'details')
    op.drop_column('interview_sessions', 'skills')
    op.drop_column('interview_sessions', 'experience_level')
    op.drop_column('interview_sessions', 'question_focus')

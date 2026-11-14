"""Add local accounts and revocable access-token sessions.

Existing interview rows retain their owner UUID. They are not linked to a new
account automatically; see the README before migrating an existing database.
"""
from alembic import op
import sqlalchemy as sa

revision = '4d2e9a1b8c10'
down_revision = '2629668340dc'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('users',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('email', sa.String(320), nullable=False),
        sa.Column('full_name', sa.String(120), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_table('auth_sessions',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_auth_sessions_user_id', 'auth_sessions', ['user_id'])
    if op.get_bind().dialect.name == 'postgresql':
        op.execute('ALTER TABLE users ENABLE ROW LEVEL SECURITY')
        op.execute('ALTER TABLE auth_sessions ENABLE ROW LEVEL SECURITY')
        # New inserts must reference a local user. Legacy rows are preserved but
        # unclaimed. NOT VALID avoids silently deleting or reassigning them.
        op.execute('ALTER TABLE interview_sessions ADD CONSTRAINT fk_interview_sessions_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE NOT VALID')


def downgrade():
    if op.get_bind().dialect.name == 'postgresql':
        op.drop_constraint('fk_interview_sessions_user', 'interview_sessions', type_='foreignkey')
    op.drop_index('ix_auth_sessions_user_id', table_name='auth_sessions')
    op.drop_table('auth_sessions')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')

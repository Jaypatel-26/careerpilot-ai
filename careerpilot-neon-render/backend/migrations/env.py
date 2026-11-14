from alembic import context
from sqlalchemy import engine_from_config, pool
from app.core.config import get_settings
from app.db.session import Base
import app.models  # noqa: F401 — registers model metadata

config = context.config
url = get_settings().migration_url
if not url:
    raise RuntimeError("DATABASE_URL must be configured before running migrations")
target_metadata = Base.metadata


def run_migrations_offline():
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    options = config.get_section(config.config_ini_section) or {}
    options["sqlalchemy.url"] = url
    connectable = engine_from_config(options, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

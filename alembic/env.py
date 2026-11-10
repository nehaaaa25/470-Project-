"""Alembic migrations. The database URL comes from .env (via app.config), not alembic.ini.

Make a migration after changing models:   alembic revision --autogenerate -m "add material catalogue"
Apply it to MySQL:                        alembic upgrade head
"""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.config import settings
from app.models import Base  # importing app.models registers every table

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _url_string() -> str:
    url = settings.sqlalchemy_url
    return url if isinstance(url, str) else url.render_as_string(hide_password=False)


def run_migrations_offline() -> None:
    context.configure(
        url=_url_string(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(settings.sqlalchemy_url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            render_as_batch=connection.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

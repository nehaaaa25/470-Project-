"""The Alembic migrations create exactly the tables the models describe, and the seed script works."""
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, inspect, select

from app.config import BASE_DIR
from app.database import Base, SessionLocal, engine
from app.models import CollectionCentre, MaterialCategory, User
from scripts import seed_demo


def test_migrations_match_models():
    Base.metadata.drop_all(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")
    command.upgrade(Config(str(BASE_DIR / "alembic.ini")), "head")

    migrated = set(inspect(create_engine(engine.url)).get_table_names()) - {"alembic_version"}
    assert migrated == set(Base.metadata.tables)


def test_seed_is_repeatable():
    with SessionLocal() as db:
        seed_demo.seed_reference_data(db)
        seed_demo.seed_reference_data(db)  # running twice must not duplicate anything
        seed_demo.seed_demo_users(db)
        seed_demo.seed_demo_users(db)
        assert db.scalar(select(func.count()).select_from(MaterialCategory)) == len(seed_demo.MATERIALS)
        assert db.scalar(select(func.count()).select_from(CollectionCentre)) == len(seed_demo.CENTRES)
        assert db.scalar(select(func.count()).select_from(User)) == len(seed_demo.DEMO_USERS)

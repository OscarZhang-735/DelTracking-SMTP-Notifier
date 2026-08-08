from pathlib import Path

from alembic import command
from alembic.config import Config

from app.database import ensure_sqlite_parent


def build_alembic_config(database_url: str) -> Config:
    backend_root = Path(__file__).resolve().parents[1]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def upgrade_database(database_url: str) -> None:
    ensure_sqlite_parent(database_url)
    config = build_alembic_config(database_url)
    command.upgrade(config, "head")

from pathlib import Path

from alembic import command
from sqlalchemy import inspect, select, text

from app.bootstrap import bootstrap_database
from app.core.config import Settings
from app.core.security import verify_password
from app.database import Database
from app.migrations import build_alembic_config, upgrade_database
from app.models import Admin, AppSettings, TrackingItem

EXPECTED_TABLES = {
    "admins",
    "alembic_version",
    "app_settings",
    "job_run_items",
    "job_runs",
    "notification_outbox",
    "recipients",
    "trace_events",
    "tracking_items",
    "tracking_recipients",
}


def sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.as_posix()}"


def test_migration_is_repeatable_and_matches_models(tmp_path: Path) -> None:
    database_url = sqlite_url(tmp_path / "nested" / "database.sqlite3")

    upgrade_database(database_url)
    upgrade_database(database_url)

    database = Database(database_url)
    assert set(inspect(database.engine).get_table_names()) == EXPECTED_TABLES
    command.check(build_alembic_config(database_url))
    database.dispose()


def test_bootstrap_and_sqlite_data_survive_reopen(tmp_path: Path) -> None:
    database_url = sqlite_url(tmp_path / "persistent.sqlite3")
    settings = Settings(
        _env_file=None,
        database_url=database_url,
        admin_username="operator",
        admin_password="a-strong-bootstrap-password",
        schedule_interval_minutes=45,
        app_timezone="Asia/Shanghai",
    )

    upgrade_database(database_url)
    database = Database(database_url)
    bootstrap_database(database, settings)
    bootstrap_database(database, settings)

    with database.engine.connect() as connection:
        assert connection.execute(text("PRAGMA journal_mode")).scalar_one().lower() == "wal"
        assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1

    with database.session() as session:
        admin = session.scalar(select(Admin))
        app_settings = session.get(AppSettings, 1)
        assert admin is not None
        assert admin.username == "operator"
        assert verify_password("a-strong-bootstrap-password", admin.password_hash)
        assert app_settings is not None
        assert app_settings.schedule_interval_minutes == 45
        session.add(TrackingItem(tracking_number="1024658760"))

    database.dispose()

    reopened = Database(database_url)
    with reopened.session() as session:
        assert session.scalar(select(TrackingItem.tracking_number)) == "1024658760"
        assert len(session.scalars(select(Admin)).all()) == 1
        assert len(session.scalars(select(AppSettings)).all()) == 1
    reopened.dispose()

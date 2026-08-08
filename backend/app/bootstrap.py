from sqlalchemy import select

from app.core.config import Settings
from app.core.security import hash_password
from app.database import Database
from app.models import Admin, AppSettings


def bootstrap_database(database: Database, settings: Settings) -> None:
    """Create singleton application data without replacing existing values."""
    with database.session() as session:
        app_settings = session.get(AppSettings, 1)
        if app_settings is None:
            session.add(
                AppSettings(
                    id=1,
                    schedule_interval_minutes=settings.schedule_interval_minutes,
                    timezone=settings.app_timezone,
                )
            )

        admin = session.scalar(select(Admin).limit(1))
        if admin is None and settings.admin_password is not None:
            session.add(
                Admin(
                    username=settings.admin_username,
                    password_hash=hash_password(settings.admin_password.get_secret_value()),
                )
            )

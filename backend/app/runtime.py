from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import Any

from sqlalchemy import select

from app.bootstrap import bootstrap_database
from app.core.config import Settings
from app.core.security import SecretCipher
from app.database import Database
from app.integrations.nextsls import NextSlsBusinessError, NextSlsClient
from app.migrations import upgrade_database
from app.models import AppSettings
from app.services.notifications import (
    EmailSender,
    OutboxDispatcher,
    build_smtp_sender,
)
from app.services.scheduler import TrackingScheduler
from app.services.tracking_jobs import TrackingJobRunner, TrackingProvider


class UnavailableTrackingProvider:
    async def track(self, _tracking_number: str) -> Any:
        raise NextSlsBusinessError("TRACKING_APP_ID is not configured")


def unavailable_email_sender(_settings: AppSettings) -> EmailSender:
    raise ValueError("SMTP_ENCRYPTION_KEY is not configured")


@dataclass(slots=True)
class AppServices:
    settings: Settings
    database: Database
    provider: TrackingProvider
    outbox_dispatcher: OutboxDispatcher
    runner: TrackingJobRunner
    scheduler: TrackingScheduler
    smtp_cipher: SecretCipher | None

    @classmethod
    def build(cls, settings: Settings) -> AppServices:
        upgrade_database(settings.database_url)
        database = Database(settings.database_url)
        bootstrap_database(database, settings)

        smtp_cipher = (
            SecretCipher(settings.smtp_encryption_key.get_secret_value())
            if settings.smtp_encryption_key is not None
            else None
        )
        sender_factory = (
            partial(build_smtp_sender, cipher=smtp_cipher)
            if smtp_cipher is not None
            else unavailable_email_sender
        )
        outbox_dispatcher = OutboxDispatcher(database, sender_factory)

        provider: TrackingProvider
        if settings.tracking_app_id is None:
            provider = UnavailableTrackingProvider()
        else:
            provider = NextSlsClient(settings.tracking_app_id.get_secret_value())

        runner = TrackingJobRunner(
            database,
            provider,
            outbox_dispatcher=outbox_dispatcher,
        )
        scheduler = TrackingScheduler(runner, outbox_dispatcher=outbox_dispatcher)
        return cls(
            settings=settings,
            database=database,
            provider=provider,
            outbox_dispatcher=outbox_dispatcher,
            runner=runner,
            scheduler=scheduler,
            smtp_cipher=smtp_cipher,
        )

    def start(self) -> None:
        with self.database.session() as session:
            app_settings = session.scalar(select(AppSettings).limit(1))
            if app_settings is None:
                raise RuntimeError("application settings are missing")
            self.scheduler.configure_from_settings(app_settings)
        self.scheduler.start()

    async def shutdown(self) -> None:
        self.scheduler.shutdown()
        close = getattr(self.provider, "close", None)
        if close is not None:
            await close()
        self.database.dispose()

    def build_email_sender(self, app_settings: AppSettings) -> EmailSender:
        if self.smtp_cipher is None:
            raise ValueError("SMTP_ENCRYPTION_KEY is not configured")
        return build_smtp_sender(app_settings, self.smtp_cipher)

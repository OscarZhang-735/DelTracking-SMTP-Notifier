from __future__ import annotations

from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.models import AppSettings
from app.services.notifications import OutboxDispatcher
from app.services.tracking_jobs import JobRunOutcome, TrackingJobRunner

TRACKING_JOB_ID = "tracking-query"
OUTBOX_JOB_ID = "notification-outbox"


class TrackingScheduler:
    def __init__(
        self,
        runner: TrackingJobRunner,
        *,
        outbox_dispatcher: OutboxDispatcher | None = None,
        scheduler: AsyncIOScheduler | None = None,
    ) -> None:
        self._runner = runner
        self._outbox_dispatcher = outbox_dispatcher
        self._scheduler = scheduler or AsyncIOScheduler()

    @property
    def scheduler(self) -> AsyncIOScheduler:
        return self._scheduler

    def configure(self, *, interval_minutes: int, enabled: bool, timezone: str) -> None:
        if not 5 <= interval_minutes <= 1440:
            raise ValueError("interval_minutes must be between 5 and 1440")
        zone = ZoneInfo(timezone)
        self._scheduler.add_job(
            self._scheduled_run,
            "interval",
            minutes=interval_minutes,
            id=TRACKING_JOB_ID,
            replace_existing=True,
            coalesce=True,
            max_instances=1,
            timezone=zone,
        )
        if not enabled:
            self._scheduler.pause_job(TRACKING_JOB_ID)
        if self._outbox_dispatcher is not None:
            self._scheduler.add_job(
                self._dispatch_outbox,
                "interval",
                minutes=1,
                id=OUTBOX_JOB_ID,
                replace_existing=True,
                coalesce=True,
                max_instances=1,
                timezone=zone,
            )

    def configure_from_settings(self, settings: AppSettings) -> None:
        self.configure(
            interval_minutes=settings.schedule_interval_minutes,
            enabled=settings.schedule_enabled,
            timezone=settings.timezone,
        )

    def start(self) -> None:
        if not self._scheduler.running:
            self._scheduler.start()

    def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    def pause(self) -> None:
        self._scheduler.pause_job(TRACKING_JOB_ID)

    def resume(self) -> None:
        self._scheduler.resume_job(TRACKING_JOB_ID)

    async def run_now(self, tracking_item_ids: list[int] | None = None) -> JobRunOutcome:
        return await self._runner.run("manual", tracking_item_ids=tracking_item_ids)

    async def _scheduled_run(self) -> None:
        await self._runner.run("scheduled")

    async def _dispatch_outbox(self) -> None:
        if self._outbox_dispatcher is not None:
            await self._outbox_dispatcher.dispatch_due()

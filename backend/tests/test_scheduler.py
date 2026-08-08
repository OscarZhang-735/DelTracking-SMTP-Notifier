import asyncio
from collections.abc import Callable
from typing import Any

import pytest

from app.services.notifications import DispatchSummary
from app.services.scheduler import OUTBOX_JOB_ID, TRACKING_JOB_ID, TrackingScheduler
from app.services.tracking_jobs import JobRunOutcome


class FakeRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[int] | None]] = []

    async def run(
        self,
        trigger: str,
        *,
        tracking_item_ids: list[int] | None = None,
    ) -> JobRunOutcome:
        self.calls.append((trigger, tracking_item_ids))
        return JobRunOutcome(
            job_run_id=1,
            status="completed",
            total_count=0,
            success_count=0,
            failure_count=0,
            changed_count=0,
        )


class FakeScheduler:
    def __init__(self) -> None:
        self.running = False
        self.added: list[dict[str, Any]] = []
        self.paused: list[str] = []
        self.resumed: list[str] = []
        self.shutdown_wait: bool | None = None

    def add_job(self, function: Callable[..., Any], trigger: str, **kwargs: Any) -> None:
        self.added.append({"function": function, "trigger": trigger, **kwargs})

    def pause_job(self, job_id: str) -> None:
        self.paused.append(job_id)

    def resume_job(self, job_id: str) -> None:
        self.resumed.append(job_id)

    def start(self) -> None:
        self.running = True

    def shutdown(self, *, wait: bool) -> None:
        self.running = False
        self.shutdown_wait = wait


class FakeDispatcher:
    def __init__(self) -> None:
        self.calls = 0

    async def dispatch_due(self) -> DispatchSummary:
        self.calls += 1
        return DispatchSummary(selected=0, sent=0, failed=0)


def test_scheduler_configures_interval_pause_and_manual_run() -> None:
    runner = FakeRunner()
    fake = FakeScheduler()
    dispatcher = FakeDispatcher()
    scheduler = TrackingScheduler(  # type: ignore[arg-type]
        runner,
        outbox_dispatcher=dispatcher,
        scheduler=fake,
    )

    scheduler.configure(interval_minutes=30, enabled=False, timezone="Asia/Shanghai")

    assert len(fake.added) == 2
    tracking_job = next(job for job in fake.added if job["id"] == TRACKING_JOB_ID)
    outbox_job = next(job for job in fake.added if job["id"] == OUTBOX_JOB_ID)
    assert tracking_job["trigger"] == "interval"
    assert tracking_job["minutes"] == 30
    assert tracking_job["coalesce"] is True
    assert tracking_job["max_instances"] == 1
    assert str(tracking_job["timezone"]) == "Asia/Shanghai"
    assert outbox_job["minutes"] == 1
    assert outbox_job["coalesce"] is True
    assert outbox_job["max_instances"] == 1
    assert fake.paused == [TRACKING_JOB_ID]

    outcome = asyncio.run(scheduler.run_now([1, 2]))
    assert outcome.status == "completed"
    assert runner.calls == [("manual", [1, 2])]

    asyncio.run(outbox_job["function"]())
    assert dispatcher.calls == 1

    scheduler.start()
    scheduler.pause()
    scheduler.resume()
    scheduler.shutdown()
    assert fake.paused[-1] == TRACKING_JOB_ID
    assert fake.resumed == [TRACKING_JOB_ID]
    assert fake.shutdown_wait is False


@pytest.mark.parametrize("minutes", [4, 1441])
def test_scheduler_rejects_out_of_range_interval(minutes: int) -> None:
    scheduler = TrackingScheduler(FakeRunner(), scheduler=FakeScheduler())  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="between 5 and 1440"):
        scheduler.configure(interval_minutes=minutes, enabled=True, timezone="Asia/Shanghai")

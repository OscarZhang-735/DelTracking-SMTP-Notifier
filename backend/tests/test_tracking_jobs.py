import asyncio
from collections.abc import Sequence
from pathlib import Path

from sqlalchemy import func, select

from app.database import Database
from app.integrations.nextsls import (
    ShipmentSnapshot,
    TraceSnapshot,
    TrackingResponse,
)
from app.migrations import upgrade_database
from app.models import (
    AppSettings,
    JobRun,
    JobRunItem,
    NotificationOutbox,
    Recipient,
    TraceEvent,
    TrackingItem,
)
from app.services.tracking_jobs import TrackingJobRunner


def sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.as_posix()}"


def response(
    tracking_number: str,
    *,
    status: str = "in_transit",
    event_info: str = "货物已发出",
) -> TrackingResponse:
    return TrackingResponse(
        shipment=ShipmentSnapshot(
            shipment_id=f"SHIP-{tracking_number}",
            client_reference=tracking_number,
            outer_carrier_code="carrier",
            outer_carrier_tracking_number=f"CARRIER-{tracking_number}",
            status=status,
            country="加拿大",
            postcode="A1A1A1",
            parcel_count=1,
            traces=(TraceSnapshot(time_raw="2026-08-08 10:00", info=event_info),),
        ),
        request_time="2026-08-08 18:00:00",
        cost_time=0.1,
    )


class MutableProvider:
    def __init__(self, responses: dict[str, TrackingResponse | Exception]) -> None:
        self.responses = responses

    async def track(self, tracking_number: str) -> TrackingResponse:
        result = self.responses[tracking_number]
        if isinstance(result, Exception):
            raise result
        return result


def create_database(path: Path) -> Database:
    database_url = sqlite_url(path)
    upgrade_database(database_url)
    database = Database(database_url)
    with database.session() as session:
        session.add(AppSettings(id=1))
    return database


def test_first_query_builds_baseline_and_second_change_queues_one_digest(tmp_path: Path) -> None:
    database = create_database(tmp_path / "baseline.sqlite3")
    with database.session() as session:
        recipient = Recipient(name="收件人", email="recipient@example.com")
        tracking_item = TrackingItem(tracking_number="TRACK-001", recipients=[recipient])
        session.add(tracking_item)

    provider = MutableProvider({"TRACK-001": response("TRACK-001")})
    runner = TrackingJobRunner(database, provider)

    baseline = asyncio.run(runner.run("scheduled"))
    assert baseline.status == "completed"
    assert baseline.changed_count == 0
    with database.session() as session:
        tracking_item = session.scalar(select(TrackingItem))
        assert tracking_item is not None
        assert tracking_item.baseline_initialized
        assert session.scalar(select(func.count()).select_from(NotificationOutbox)) == 0

    provider.responses["TRACK-001"] = response(
        "TRACK-001",
        status="delivered",
    )
    changed = asyncio.run(runner.run("manual"))

    assert changed.changed_count == 1
    with database.session() as session:
        notifications = list(session.scalars(select(NotificationOutbox)))
        assert len(notifications) == 1
        assert notifications[0].recipient_email == "recipient@example.com"
        assert "TRACK-001" in notifications[0].body_text
        assert "已签收" in notifications[0].body_text
        assert session.scalar(select(func.count()).select_from(TraceEvent)) == 1

    unchanged = asyncio.run(runner.run("scheduled"))
    assert unchanged.changed_count == 0
    with database.session() as session:
        assert session.scalar(select(func.count()).select_from(NotificationOutbox)) == 1

    database.dispose()


def test_each_recipient_only_receives_linked_tracking_changes(tmp_path: Path) -> None:
    database = create_database(tmp_path / "recipients.sqlite3")
    with database.session() as session:
        recipient_a = Recipient(name="A", email="a@example.com")
        recipient_b = Recipient(name="B", email="b@example.com")
        session.add_all(
            [
                TrackingItem(
                    tracking_number="TRACK-A",
                    baseline_initialized=True,
                    shipment_status="ready",
                    recipients=[recipient_a],
                ),
                TrackingItem(
                    tracking_number="TRACK-B",
                    baseline_initialized=True,
                    shipment_status="ready",
                    recipients=[recipient_b],
                ),
            ]
        )

    provider = MutableProvider(
        {
            "TRACK-A": response("TRACK-A", event_info="A 已发出"),
            "TRACK-B": response("TRACK-B", event_info="B 已发出"),
        }
    )
    runner = TrackingJobRunner(database, provider)
    outcome = asyncio.run(runner.run("scheduled"))

    assert outcome.changed_count == 2
    with database.session() as session:
        notifications = {
            notification.recipient_email: notification.body_text
            for notification in session.scalars(select(NotificationOutbox))
        }
        assert "TRACK-A" in notifications["a@example.com"]
        assert "TRACK-B" not in notifications["a@example.com"]
        assert "TRACK-B" in notifications["b@example.com"]
        assert "TRACK-A" not in notifications["b@example.com"]

    database.dispose()


def test_one_failure_does_not_overwrite_success_or_abort_other_items(tmp_path: Path) -> None:
    database = create_database(tmp_path / "partial.sqlite3")
    with database.session() as session:
        session.add_all(
            [
                TrackingItem(
                    tracking_number="TRACK-FAIL",
                    baseline_initialized=True,
                    shipment_status="delivered",
                    shipment_id="KEEP-ME",
                ),
                TrackingItem(tracking_number="TRACK-OK"),
            ]
        )

    provider = MutableProvider(
        {
            "TRACK-FAIL": RuntimeError("provider unavailable"),
            "TRACK-OK": response("TRACK-OK"),
        }
    )
    outcome = asyncio.run(TrackingJobRunner(database, provider).run("scheduled"))

    assert outcome.status == "partial"
    assert outcome.success_count == 1
    assert outcome.failure_count == 1
    with database.session() as session:
        failed = session.scalar(
            select(TrackingItem).where(TrackingItem.tracking_number == "TRACK-FAIL")
        )
        assert failed is not None
        assert failed.shipment_status == "delivered"
        assert failed.shipment_id == "KEEP-ME"
        assert failed.last_error == "provider unavailable"
        run_items = list(session.scalars(select(JobRunItem).order_by(JobRunItem.id)))
        assert [item.status for item in run_items] == ["failed", "succeeded"]

    database.dispose()


class BlockingProvider:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def track(self, tracking_number: str) -> TrackingResponse:
        self.started.set()
        await self.release.wait()
        return response(tracking_number)


def test_overlapping_job_is_skipped_and_audited(tmp_path: Path) -> None:
    database = create_database(tmp_path / "overlap.sqlite3")
    with database.session() as session:
        session.add(TrackingItem(tracking_number="TRACK-001"))

    async def scenario() -> Sequence[str]:
        provider = BlockingProvider()
        runner = TrackingJobRunner(database, provider)
        first_task = asyncio.create_task(runner.run("scheduled"))
        await provider.started.wait()
        skipped = await runner.run("manual")
        provider.release.set()
        completed = await first_task
        return skipped.status, completed.status

    statuses = asyncio.run(scenario())
    assert statuses == ("skipped", "completed")
    with database.session() as session:
        runs = list(session.scalars(select(JobRun).order_by(JobRun.id)))
        assert [run.status for run in runs] == ["completed", "skipped"]
        skipped_run = next(run for run in runs if run.status == "skipped")
        assert "already running" in (skipped_run.error_summary or "")

    database.dispose()

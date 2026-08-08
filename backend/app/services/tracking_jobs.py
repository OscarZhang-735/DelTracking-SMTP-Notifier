from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import Database
from app.integrations.nextsls import TrackingResponse
from app.models import JobRun, JobRunItem, TrackingItem
from app.services.notifications import (
    OutboxDispatcher,
    TrackingChange,
    queue_digest,
)
from app.services.tracking_snapshots import apply_shipment_snapshot, record_tracking_failure


class TrackingProvider(Protocol):
    async def track(self, tracking_number: str) -> TrackingResponse: ...


@dataclass(frozen=True, slots=True)
class TrackingTarget:
    id: int
    tracking_number: str


@dataclass(frozen=True, slots=True)
class QueryResult:
    target: TrackingTarget
    response: TrackingResponse | None = None
    error: Exception | None = None


@dataclass(frozen=True, slots=True)
class JobRunOutcome:
    job_run_id: int
    status: str
    total_count: int
    success_count: int
    failure_count: int
    changed_count: int


@dataclass(slots=True)
class RecipientChanges:
    recipient_id: int
    recipient_email: str
    changes: list[TrackingChange] = field(default_factory=list)


class TrackingJobRunner:
    def __init__(
        self,
        database: Database,
        provider: TrackingProvider,
        *,
        outbox_dispatcher: OutboxDispatcher | None = None,
    ) -> None:
        self._database = database
        self._provider = provider
        self._outbox_dispatcher = outbox_dispatcher
        self._lock = asyncio.Lock()

    async def run(
        self,
        trigger: str,
        *,
        tracking_item_ids: list[int] | None = None,
    ) -> JobRunOutcome:
        if self._lock.locked():
            return self._record_skipped(trigger)

        async with self._lock:
            run_id, targets = self._begin_run(trigger, tracking_item_ids)
            results = await asyncio.gather(*(self._query(target) for target in targets))
            try:
                outcome = self._persist_results(run_id, results)
            except Exception as exc:
                self._mark_run_failed(run_id, exc)
                raise

            if self._outbox_dispatcher is not None:
                await self._outbox_dispatcher.dispatch_due()
            return outcome

    def _begin_run(
        self,
        trigger: str,
        tracking_item_ids: list[int] | None,
    ) -> tuple[int, list[TrackingTarget]]:
        normalized_trigger = trigger.strip()[:20]
        if not normalized_trigger:
            raise ValueError("trigger must not be blank")

        with self._database.session() as session:
            statement = select(TrackingItem.id, TrackingItem.tracking_number)
            if tracking_item_ids is None:
                statement = statement.where(TrackingItem.enabled.is_(True))
            else:
                statement = statement.where(TrackingItem.id.in_(set(tracking_item_ids)))
            rows = session.execute(statement.order_by(TrackingItem.id)).all()
            targets = [
                TrackingTarget(id=row.id, tracking_number=row.tracking_number) for row in rows
            ]

            job_run = JobRun(
                trigger=normalized_trigger,
                status="running",
                total_count=len(targets),
            )
            session.add(job_run)
            session.flush()
            return job_run.id, targets

    async def _query(self, target: TrackingTarget) -> QueryResult:
        try:
            response = await self._provider.track(target.tracking_number)
        except Exception as exc:
            return QueryResult(target=target, error=exc)
        return QueryResult(target=target, response=response)

    def _persist_results(self, run_id: int, results: list[QueryResult]) -> JobRunOutcome:
        checked_at = datetime.now(UTC)
        success_count = 0
        failure_count = 0
        changed_count = 0
        recipient_changes: dict[int, RecipientChanges] = {}

        with self._database.session() as session:
            job_run = session.get(JobRun, run_id)
            if job_run is None:
                raise RuntimeError(f"job run {run_id} no longer exists")

            for result in results:
                tracking_item = session.scalar(
                    select(TrackingItem)
                    .options(selectinload(TrackingItem.recipients))
                    .where(TrackingItem.id == result.target.id)
                )
                if tracking_item is None:
                    failure_count += 1
                    session.add(
                        JobRunItem(
                            job_run_id=run_id,
                            tracking_item_id=None,
                            tracking_number=result.target.tracking_number,
                            status="failed",
                            error="Tracking item was deleted during the query",
                            checked_at=checked_at,
                        )
                    )
                    continue

                if result.error is not None or result.response is None:
                    failure_count += 1
                    error_message = str(result.error or "Provider returned no response")
                    record_tracking_failure(tracking_item, error_message, checked_at=checked_at)
                    session.add(
                        JobRunItem(
                            job_run_id=run_id,
                            tracking_item_id=tracking_item.id,
                            tracking_number=tracking_item.tracking_number,
                            status="failed",
                            error=error_message[:2000],
                            checked_at=checked_at,
                        )
                    )
                    continue

                success_count += 1
                had_baseline = tracking_item.baseline_initialized
                applied = apply_shipment_snapshot(
                    session,
                    tracking_item,
                    result.response.shipment,
                    checked_at=checked_at,
                )
                tracking_item.baseline_initialized = True
                changed = had_baseline and (applied.status_changed or bool(applied.added_events))
                if changed:
                    changed_count += 1
                    change = TrackingChange(
                        tracking_number=tracking_item.tracking_number,
                        previous_status=applied.previous_status,
                        current_status=applied.current_status,
                        added_events=applied.added_events,
                    )
                    for recipient in tracking_item.recipients:
                        if not recipient.enabled:
                            continue
                        digest = recipient_changes.setdefault(
                            recipient.id,
                            RecipientChanges(
                                recipient_id=recipient.id,
                                recipient_email=recipient.email,
                            ),
                        )
                        digest.changes.append(change)

                session.add(
                    JobRunItem(
                        job_run_id=run_id,
                        tracking_item_id=tracking_item.id,
                        tracking_number=tracking_item.tracking_number,
                        status="succeeded",
                        changed=changed,
                        added_event_count=len(applied.added_events),
                        previous_status=applied.previous_status,
                        current_status=applied.current_status,
                        checked_at=checked_at,
                    )
                )

            for digest in recipient_changes.values():
                queue_digest(
                    session,
                    job_run_id=run_id,
                    recipient_id=digest.recipient_id,
                    recipient_email=digest.recipient_email,
                    changes=digest.changes,
                )

            status = self._completion_status(success_count, failure_count)
            job_run.status = status
            job_run.finished_at = checked_at
            job_run.success_count = success_count
            job_run.failure_count = failure_count
            job_run.changed_count = changed_count
            job_run.error_summary = (
                f"{failure_count} tracking queries failed" if failure_count else None
            )

        return JobRunOutcome(
            job_run_id=run_id,
            status=status,
            total_count=len(results),
            success_count=success_count,
            failure_count=failure_count,
            changed_count=changed_count,
        )

    def _record_skipped(self, trigger: str) -> JobRunOutcome:
        with self._database.session() as session:
            job_run = JobRun(
                trigger=trigger.strip()[:20] or "unknown",
                status="skipped",
                started_at=datetime.now(UTC),
                finished_at=datetime.now(UTC),
                error_summary="Another tracking job is already running",
            )
            session.add(job_run)
            session.flush()
            run_id = job_run.id
        return JobRunOutcome(
            job_run_id=run_id,
            status="skipped",
            total_count=0,
            success_count=0,
            failure_count=0,
            changed_count=0,
        )

    def _mark_run_failed(self, run_id: int, error: Exception) -> None:
        with self._database.session() as session:
            job_run = session.get(JobRun, run_id)
            if job_run is None:
                return
            job_run.status = "failed"
            job_run.finished_at = datetime.now(UTC)
            job_run.error_summary = str(error).strip()[:2000] or type(error).__name__

    @staticmethod
    def _completion_status(success_count: int, failure_count: int) -> str:
        if failure_count == 0:
            return "completed"
        if success_count == 0:
            return "failed"
        return "partial"

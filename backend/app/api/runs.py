from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import get_db, get_services, require_admin, require_csrf
from app.api.schemas import (
    JobRunDetailResponse,
    JobRunItemResponse,
    JobRunListResponse,
    JobRunResponse,
    NotificationResponse,
    RetryNotificationResponse,
)
from app.models import JobRun, NotificationOutbox
from app.runtime import AppServices

router = APIRouter(tags=["operations"], dependencies=[Depends(require_admin)])


def serialize_run(run: JobRun) -> JobRunResponse:
    return JobRunResponse(
        id=run.id,
        trigger=run.trigger,
        status=run.status,
        started_at=run.started_at,
        finished_at=run.finished_at,
        total_count=run.total_count,
        success_count=run.success_count,
        failure_count=run.failure_count,
        changed_count=run.changed_count,
        error_summary=run.error_summary,
    )


@router.get("/runs", response_model=JobRunListResponse)
async def list_runs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_db),
) -> JobRunListResponse:
    total = session.scalar(select(func.count()).select_from(JobRun)) or 0
    runs = list(
        session.scalars(
            select(JobRun)
            .order_by(JobRun.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return JobRunListResponse(
        items=[serialize_run(run) for run in runs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/runs/{run_id}", response_model=JobRunDetailResponse)
async def get_run(run_id: int, session: Session = Depends(get_db)) -> JobRunDetailResponse:
    run = session.scalar(
        select(JobRun)
        .options(selectinload(JobRun.items), selectinload(JobRun.notifications))
        .where(JobRun.id == run_id)
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Job run not found")
    base = serialize_run(run).model_dump()
    return JobRunDetailResponse(
        **base,
        items=[
            JobRunItemResponse(
                id=item.id,
                tracking_item_id=item.tracking_item_id,
                tracking_number=item.tracking_number,
                status=item.status,
                changed=item.changed,
                added_event_count=item.added_event_count,
                previous_status=item.previous_status,
                current_status=item.current_status,
                error=item.error,
                checked_at=item.checked_at,
            )
            for item in sorted(run.items, key=lambda item: item.id)
        ],
        notifications=[
            NotificationResponse(
                id=notification.id,
                recipient_email=notification.recipient_email,
                subject=notification.subject,
                status=notification.status,
                attempt_count=notification.attempt_count,
                next_attempt_at=notification.next_attempt_at,
                last_error=notification.last_error,
                created_at=notification.created_at,
                sent_at=notification.sent_at,
            )
            for notification in sorted(run.notifications, key=lambda item: item.id)
        ],
    )


@router.post(
    "/notifications/{notification_id}/retry",
    response_model=RetryNotificationResponse,
    dependencies=[Depends(require_csrf)],
)
async def retry_notification(
    notification_id: int,
    services: AppServices = Depends(get_services),
    session: Session = Depends(get_db),
) -> RetryNotificationResponse:
    if session.get(NotificationOutbox, notification_id) is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    if not services.outbox_dispatcher.retry_now(notification_id):
        raise HTTPException(status_code=409, detail="Sent notification cannot be retried")
    summary = await services.outbox_dispatcher.dispatch_due(notification_ids=[notification_id])
    return RetryNotificationResponse(
        notification_id=notification_id,
        selected=summary.selected,
        sent=summary.sent,
        failed=summary.failed,
    )

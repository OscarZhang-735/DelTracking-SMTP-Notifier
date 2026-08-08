from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import get_db, get_services, require_admin, require_csrf
from app.api.schemas import (
    QueryRunResponse,
    RecipientBrief,
    TraceResponse,
    TrackingCreate,
    TrackingListResponse,
    TrackingResponse,
    TrackingUpdate,
)
from app.integrations.nextsls import status_label
from app.models import Recipient, TrackingItem
from app.runtime import AppServices

router = APIRouter(
    prefix="/trackings",
    tags=["trackings"],
    dependencies=[Depends(require_admin)],
)


def tracking_query():
    return select(TrackingItem).options(
        selectinload(TrackingItem.recipients),
        selectinload(TrackingItem.trace_events),
    )


def serialize_tracking(item: TrackingItem, *, include_traces: bool = True) -> TrackingResponse:
    traces = (
        [
            TraceResponse(id=event.id, time_raw=event.event_time_raw, info=event.info)
            for event in sorted(item.trace_events, key=lambda event: event.id, reverse=True)
        ]
        if include_traces
        else []
    )
    return TrackingResponse(
        id=item.id,
        tracking_number=item.tracking_number,
        enabled=item.enabled,
        notes=item.notes,
        baseline_initialized=item.baseline_initialized,
        shipment_id=item.shipment_id,
        client_reference=item.client_reference,
        outer_carrier_code=item.outer_carrier_code,
        outer_carrier_tracking_number=item.outer_carrier_tracking_number,
        shipment_status=item.shipment_status,
        localized_status=status_label(item.shipment_status),
        country=item.country,
        postcode=item.postcode,
        parcel_count=item.parcel_count,
        last_checked_at=item.last_checked_at,
        last_success_at=item.last_success_at,
        last_error=item.last_error,
        recipients=[
            RecipientBrief(
                id=recipient.id,
                name=recipient.name,
                email=recipient.email,
                enabled=recipient.enabled,
            )
            for recipient in sorted(item.recipients, key=lambda recipient: recipient.id)
        ],
        traces=traces,
    )


def resolve_recipients(session: Session, recipient_ids: list[int]) -> list[Recipient]:
    unique_ids = set(recipient_ids)
    if not unique_ids:
        return []
    recipients = list(
        session.scalars(select(Recipient).where(Recipient.id.in_(unique_ids)).order_by(Recipient.id))
    )
    if len(recipients) != len(unique_ids):
        raise HTTPException(status_code=422, detail="One or more recipients do not exist")
    return recipients


@router.get("", response_model=TrackingListResponse)
async def list_trackings(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, max_length=100),
    shipment_status: str | None = Query(default=None, max_length=50),
    enabled: bool | None = None,
    session: Session = Depends(get_db),
) -> TrackingListResponse:
    filters = []
    if search:
        term = f"%{search.strip()}%"
        filters.append(
            or_(
                TrackingItem.tracking_number.ilike(term),
                TrackingItem.shipment_id.ilike(term),
                TrackingItem.client_reference.ilike(term),
            )
        )
    if shipment_status:
        filters.append(TrackingItem.shipment_status == shipment_status)
    if enabled is not None:
        filters.append(TrackingItem.enabled.is_(enabled))

    total = session.scalar(select(func.count()).select_from(TrackingItem).where(*filters)) or 0
    statement = (
        tracking_query()
        .where(*filters)
        .order_by(TrackingItem.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = list(session.scalars(statement))
    return TrackingListResponse(
        items=[serialize_tracking(item, include_traces=False) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "",
    response_model=TrackingResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def create_tracking(
    payload: TrackingCreate,
    session: Session = Depends(get_db),
) -> TrackingResponse:
    item = TrackingItem(
        tracking_number=payload.tracking_number,
        enabled=payload.enabled,
        notes=payload.notes,
        recipients=resolve_recipients(session, payload.recipient_ids),
    )
    session.add(item)
    try:
        session.flush()
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Tracking number already exists") from exc
    session.refresh(item)
    return serialize_tracking(item)


@router.get("/{tracking_id}", response_model=TrackingResponse)
async def get_tracking(
    tracking_id: int,
    session: Session = Depends(get_db),
) -> TrackingResponse:
    item = session.scalar(tracking_query().where(TrackingItem.id == tracking_id))
    if item is None:
        raise HTTPException(status_code=404, detail="Tracking item not found")
    return serialize_tracking(item)


@router.patch(
    "/{tracking_id}",
    response_model=TrackingResponse,
    dependencies=[Depends(require_csrf)],
)
async def update_tracking(
    tracking_id: int,
    payload: TrackingUpdate,
    session: Session = Depends(get_db),
) -> TrackingResponse:
    item = session.scalar(tracking_query().where(TrackingItem.id == tracking_id))
    if item is None:
        raise HTTPException(status_code=404, detail="Tracking item not found")

    updates = payload.model_dump(exclude_unset=True)
    recipient_ids = updates.pop("recipient_ids", None)
    for field_name, value in updates.items():
        setattr(item, field_name, value)
    if recipient_ids is not None:
        item.recipients = resolve_recipients(session, recipient_ids)
    try:
        session.flush()
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Tracking number already exists") from exc
    return serialize_tracking(item)


@router.delete(
    "/{tracking_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def delete_tracking(
    tracking_id: int,
    session: Session = Depends(get_db),
) -> Response:
    item = session.get(TrackingItem, tracking_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Tracking item not found")
    session.delete(item)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{tracking_id}/query",
    response_model=QueryRunResponse,
    dependencies=[Depends(require_csrf)],
)
async def query_tracking(
    tracking_id: int,
    services: AppServices = Depends(get_services),
    session: Session = Depends(get_db),
) -> QueryRunResponse:
    if session.get(TrackingItem, tracking_id) is None:
        raise HTTPException(status_code=404, detail="Tracking item not found")
    outcome = await services.scheduler.run_now([tracking_id])
    return QueryRunResponse(**asdict(outcome))


@router.post(
    "/query-all",
    response_model=QueryRunResponse,
    dependencies=[Depends(require_csrf)],
)
async def query_all(services: AppServices = Depends(get_services)) -> QueryRunResponse:
    outcome = await services.scheduler.run_now()
    return QueryRunResponse(**asdict(outcome))

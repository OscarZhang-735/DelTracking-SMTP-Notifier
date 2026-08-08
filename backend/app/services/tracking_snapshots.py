from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.nextsls import ShipmentSnapshot, TraceSnapshot
from app.models import TraceEvent, TrackingItem


@dataclass(frozen=True, slots=True)
class SnapshotApplyResult:
    previous_status: str | None
    current_status: str | None
    added_events: tuple[TraceSnapshot, ...]

    @property
    def status_changed(self) -> bool:
        return self.previous_status != self.current_status


def apply_shipment_snapshot(
    session: Session,
    tracking_item: TrackingItem,
    snapshot: ShipmentSnapshot,
    *,
    checked_at: datetime | None = None,
) -> SnapshotApplyResult:
    now = checked_at or datetime.now(UTC)
    previous_status = tracking_item.shipment_status
    if tracking_item.id is None:
        session.flush([tracking_item])

    existing_events = {
        (event_time_raw, info)
        for event_time_raw, info in session.execute(
            select(TraceEvent.event_time_raw, TraceEvent.info).where(
                TraceEvent.tracking_item_id == tracking_item.id
            )
        )
    }
    added_events: list[TraceSnapshot] = []
    for event in snapshot.traces:
        identity = (event.time_raw, event.info)
        if identity in existing_events:
            continue
        existing_events.add(identity)
        added_events.append(event)
        session.add(
            TraceEvent(
                tracking_item=tracking_item,
                event_time_raw=event.time_raw,
                info=event.info,
            )
        )

    tracking_item.shipment_id = snapshot.shipment_id
    tracking_item.client_reference = snapshot.client_reference
    tracking_item.outer_carrier_code = snapshot.outer_carrier_code
    tracking_item.outer_carrier_tracking_number = snapshot.outer_carrier_tracking_number
    tracking_item.shipment_status = snapshot.status
    tracking_item.country = snapshot.country
    tracking_item.postcode = snapshot.postcode
    tracking_item.parcel_count = snapshot.parcel_count
    tracking_item.last_checked_at = now
    tracking_item.last_success_at = now
    tracking_item.last_error = None

    return SnapshotApplyResult(
        previous_status=previous_status,
        current_status=snapshot.status,
        added_events=tuple(added_events),
    )


def record_tracking_failure(
    tracking_item: TrackingItem,
    error: str,
    *,
    checked_at: datetime | None = None,
) -> None:
    tracking_item.last_checked_at = checked_at or datetime.now(UTC)
    tracking_item.last_error = error.strip()[:2000] or "Unknown tracking error"

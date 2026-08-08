from datetime import UTC, datetime

from sqlalchemy import func, select

from app.database import Base, Database
from app.integrations.nextsls import ShipmentSnapshot, TraceSnapshot
from app.models import TraceEvent, TrackingItem
from app.services.tracking_snapshots import apply_shipment_snapshot, record_tracking_failure


def make_snapshot(
    *,
    status: str = "in_transit",
    traces: tuple[TraceSnapshot, ...] | None = None,
) -> ShipmentSnapshot:
    return ShipmentSnapshot(
        shipment_id="SHIPMENT-001",
        client_reference="TEST-001",
        outer_carrier_code="sample-carrier",
        outer_carrier_tracking_number="CARRIER-001",
        status=status,
        country="加拿大",
        postcode="A1A1A1",
        parcel_count=1,
        traces=traces
        or (
            TraceSnapshot(time_raw="2026-08-05 17:44:35", info="货物已放行"),
            TraceSnapshot(time_raw="2026-08-01 21:10:56", info="已装柜"),
        ),
    )


def test_success_snapshot_updates_fields_and_deduplicates_events() -> None:
    database = Database("sqlite:///:memory:")
    Base.metadata.create_all(database.engine)
    checked_at = datetime(2026, 8, 8, 9, 0, tzinfo=UTC)

    with database.session() as session:
        tracking_item = TrackingItem(tracking_number="TEST-001")
        session.add(tracking_item)
        session.flush()

        first = apply_shipment_snapshot(
            session,
            tracking_item,
            make_snapshot(),
            checked_at=checked_at,
        )
        session.flush()

        reordered = make_snapshot(traces=tuple(reversed(make_snapshot().traces)))
        second = apply_shipment_snapshot(session, tracking_item, reordered)

        assert first.previous_status is None
        assert first.current_status == "in_transit"
        assert first.status_changed
        assert len(first.added_events) == 2
        assert not second.status_changed
        assert second.added_events == ()
        assert tracking_item.shipment_id == "SHIPMENT-001"
        assert tracking_item.client_reference == "TEST-001"
        assert tracking_item.outer_carrier_tracking_number == "CARRIER-001"
        assert tracking_item.last_success_at is not None
        assert tracking_item.last_error is None
        assert session.scalar(select(func.count()).select_from(TraceEvent)) == 2

    database.dispose()


def test_failure_records_error_without_overwriting_successful_snapshot() -> None:
    successful_at = datetime(2026, 8, 8, 8, 0, tzinfo=UTC)
    failed_at = datetime(2026, 8, 8, 9, 0, tzinfo=UTC)
    tracking_item = TrackingItem(
        tracking_number="TEST-001",
        shipment_status="delivered",
        shipment_id="SHIPMENT-001",
        last_success_at=successful_at,
    )

    record_tracking_failure(tracking_item, " provider unavailable ", checked_at=failed_at)

    assert tracking_item.shipment_status == "delivered"
    assert tracking_item.shipment_id == "SHIPMENT-001"
    assert tracking_item.last_success_at == successful_at
    assert tracking_item.last_checked_at == failed_at
    assert tracking_item.last_error == "provider unavailable"

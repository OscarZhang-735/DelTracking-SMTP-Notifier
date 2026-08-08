from collections.abc import Generator
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.bootstrap import bootstrap_database
from app.core.config import Settings
from app.core.security import SecretCipher
from app.database import Database
from app.integrations.nextsls import ShipmentSnapshot, TraceSnapshot, TrackingResponse
from app.main import create_app
from app.migrations import upgrade_database
from app.runtime import AppServices
from app.services.notifications import OutboxDispatcher, OutgoingEmail
from app.services.scheduler import TrackingScheduler
from app.services.tracking_jobs import TrackingJobRunner


class FakeProvider:
    def __init__(self) -> None:
        self.responses: dict[str, TrackingResponse | Exception] = {}

    async def track(self, tracking_number: str) -> TrackingResponse:
        result = self.responses.get(tracking_number, tracking_response(tracking_number))
        if isinstance(result, Exception):
            raise result
        return result


@dataclass
class FakeSender:
    sent: list[OutgoingEmail] = field(default_factory=list)

    async def send(self, email: OutgoingEmail) -> None:
        self.sent.append(email)


@dataclass
class ApiHarness:
    client: TestClient
    services: AppServices
    provider: FakeProvider
    sender: FakeSender

    def login(self, password: str = "initial-password-123") -> str:
        csrf_token = self.client.get("/api/v1/auth/csrf").json()["csrf_token"]
        response = self.client.post(
            "/api/v1/auth/login",
            headers={"X-CSRF-Token": csrf_token},
            json={"username": "admin", "password": password},
        )
        assert response.status_code == 200
        return response.json()["csrf_token"]


def tracking_response(
    tracking_number: str,
    *,
    status: str = "in_transit",
) -> TrackingResponse:
    return TrackingResponse(
        shipment=ShipmentSnapshot(
            shipment_id=f"SHIP-{tracking_number}",
            client_reference=f"CLIENT-{tracking_number}",
            outer_carrier_code="carrier",
            outer_carrier_tracking_number=f"CARRIER-{tracking_number}",
            status=status,
            country="CA",
            postcode="A1A1A1",
            parcel_count=1,
            traces=(
                TraceSnapshot(
                    time_raw="2026-08-08 10:00:00",
                    info="Shipment departed",
                ),
            ),
        ),
        request_time="2026-08-08 18:00:00",
        cost_time=0.1,
    )


@pytest.fixture
def api_harness(tmp_path: Path) -> Generator[ApiHarness]:
    database_url = f"sqlite:///{(tmp_path / 'api.sqlite3').as_posix()}"
    settings = Settings(
        database_url=database_url,
        session_secret="test-session-secret",
        smtp_encryption_key=Fernet.generate_key().decode("ascii"),
        admin_username="admin",
        admin_password="initial-password-123",
        app_environment="test",
    )
    upgrade_database(database_url)
    database = Database(database_url)
    bootstrap_database(database, settings)

    provider = FakeProvider()
    sender = FakeSender()
    cipher = SecretCipher(settings.smtp_encryption_key.get_secret_value())
    dispatcher = OutboxDispatcher(database, lambda _settings: sender)
    runner = TrackingJobRunner(database, provider, outbox_dispatcher=dispatcher)
    scheduler = TrackingScheduler(runner, outbox_dispatcher=dispatcher)
    services = AppServices(
        settings=settings,
        database=database,
        provider=provider,
        outbox_dispatcher=dispatcher,
        runner=runner,
        scheduler=scheduler,
        smtp_cipher=cipher,
    )

    with TestClient(create_app(settings, services)) as client:
        yield ApiHarness(client=client, services=services, provider=provider, sender=sender)

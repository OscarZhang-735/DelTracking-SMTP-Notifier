import asyncio
import json
from pathlib import Path

import httpx
import pytest

from app.integrations.nextsls import (
    NextSlsBusinessError,
    NextSlsClient,
    NextSlsProtocolError,
    NextSlsTransportError,
    parse_tracking_response,
    status_label,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "nextsls_success.json"


def success_payload() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


async def no_sleep(_delay: float) -> None:
    return None


def test_success_response_is_parsed_and_query_is_encoded() -> None:
    async def scenario() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.params["number"] == "TEST 001"
            assert request.url.params["app"] == "test-app"
            return httpx.Response(200, json=success_payload())

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
            client = NextSlsClient("test-app", http_client=http_client, sleeper=no_sleep)
            response = await client.track(" TEST 001 ")

        assert response.shipment.shipment_id == "SHIPMENT-001"
        assert response.shipment.status == "in_transit"
        assert response.shipment.localized_status == "转运中"
        assert response.shipment.parcel_count == 1
        assert response.shipment.traces[0].time_raw == "2026-08-05 17:44:35"
        assert response.shipment.traces[0].info == "货物已放行"

    asyncio.run(scenario())


def test_optional_fields_and_empty_traces_are_accepted() -> None:
    response = parse_tracking_response(
        {
            "status": 1,
            "data": {
                "shipment": {
                    "status": "custom_status",
                    "shipment_id": False,
                    "parcel_count": False,
                    "traces": None,
                }
            },
        }
    )

    assert response.shipment.shipment_id is None
    assert response.shipment.parcel_count is None
    assert response.shipment.traces == ()
    assert response.shipment.localized_status == "未知状态（custom_status）"
    assert status_label(None) == "暂无状态"


def test_business_error_is_not_retried() -> None:
    async def scenario() -> None:
        attempts = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            return httpx.Response(200, json={"status": 0, "info": "请输入单号"})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
            client = NextSlsClient("test-app", http_client=http_client, sleeper=no_sleep)
            with pytest.raises(NextSlsBusinessError, match="请输入单号"):
                await client.track("INVALID")

        assert attempts == 1

    asyncio.run(scenario())


@pytest.mark.parametrize("status_code", [429, 500, 503])
def test_retryable_http_statuses_retry_twice(status_code: int) -> None:
    async def scenario() -> None:
        attempts = 0
        delays: list[float] = []

        async def sleeper(delay: float) -> None:
            delays.append(delay)

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                return httpx.Response(status_code, headers={"Retry-After": "0"})
            return httpx.Response(200, json=success_payload())

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
            client = NextSlsClient("test-app", http_client=http_client, sleeper=sleeper)
            response = await client.track("TEST-001")

        assert response.shipment.client_reference == "TEST-TRACKING-001"
        assert attempts == 3
        assert delays == [0.0, 0.0]

    asyncio.run(scenario())


def test_timeout_exhausts_three_attempts() -> None:
    async def scenario() -> None:
        attempts = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            raise httpx.ReadTimeout("timed out", request=request)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
            client = NextSlsClient("test-app", http_client=http_client, sleeper=no_sleep)
            with pytest.raises(NextSlsTransportError) as captured:
                await client.track("TEST-001")

        assert captured.value.attempts == 3
        assert captured.value.status_code is None
        assert attempts == 3

    asyncio.run(scenario())


def test_non_retryable_http_error_fails_immediately() -> None:
    async def scenario() -> None:
        attempts = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            return httpx.Response(404)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
            client = NextSlsClient("test-app", http_client=http_client, sleeper=no_sleep)
            with pytest.raises(NextSlsTransportError) as captured:
                await client.track("TEST-001")

        assert captured.value.status_code == 404
        assert captured.value.attempts == 1
        assert attempts == 1

    asyncio.run(scenario())


def test_malformed_json_and_missing_shipment_are_protocol_errors() -> None:
    async def scenario() -> None:
        responses = iter(
            [
                httpx.Response(200, content=b"{not-json"),
                httpx.Response(200, json={"status": 1, "data": None}),
            ]
        )

        def handler(_request: httpx.Request) -> httpx.Response:
            return next(responses)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
            client = NextSlsClient("test-app", http_client=http_client, sleeper=no_sleep)
            with pytest.raises(NextSlsProtocolError, match="malformed JSON"):
                await client.track("TEST-001")
            with pytest.raises(NextSlsProtocolError, match="data.shipment"):
                await client.track("TEST-002")

    asyncio.run(scenario())


class MeasuringTransport(httpx.AsyncBaseTransport):
    def __init__(self) -> None:
        self.active = 0
        self.maximum_active = 0
        self._lock = asyncio.Lock()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        async with self._lock:
            self.active += 1
            self.maximum_active = max(self.maximum_active, self.active)
        await asyncio.sleep(0.01)
        async with self._lock:
            self.active -= 1
        return httpx.Response(200, json=success_payload(), request=request)


def test_client_limits_concurrency_to_three() -> None:
    async def scenario() -> None:
        transport = MeasuringTransport()
        async with httpx.AsyncClient(transport=transport) as http_client:
            client = NextSlsClient("test-app", http_client=http_client, max_concurrency=3)
            await asyncio.gather(*(client.track(f"TEST-{index}") for index in range(8)))

        assert transport.maximum_active == 3

    asyncio.run(scenario())

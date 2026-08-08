from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

NEXTSLS_TRACKING_URL = "https://tracking.nextsls.com/rest/trace/tracking/lists"

STATUS_LABELS = {
    "ready": "已下单",
    "picked": "已收货",
    "in_transit": "转运中",
    "delivered": "已签收",
    "returned": "退件",
    "cancelled": "已取消",
}

SleepCallable = Callable[[float], Awaitable[None]]


class NextSlsError(RuntimeError):
    """Base class for failures returned by the NextSLS integration."""


class NextSlsBusinessError(NextSlsError):
    """The provider accepted the request but rejected the tracking query."""


class NextSlsProtocolError(NextSlsError):
    """The provider response does not match the expected JSON contract."""


class NextSlsTransportError(NextSlsError):
    """The provider could not be reached successfully."""

    def __init__(self, message: str, *, attempts: int, status_code: int | None = None) -> None:
        super().__init__(message)
        self.attempts = attempts
        self.status_code = status_code


def status_label(status: str | None) -> str:
    if not status:
        return "暂无状态"
    return STATUS_LABELS.get(status, f"未知状态（{status}）")


def _optional_text(value: Any) -> str | None:
    if value is None or value is False:
        return None
    normalized = str(value).strip()
    return normalized or None


class _TracePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    time: str
    info: str

    @field_validator("time", "info", mode="before")
    @classmethod
    def normalize_required_text(cls, value: Any) -> str:
        normalized = _optional_text(value)
        if normalized is None:
            raise ValueError("trace time and info must not be blank")
        return normalized


class _ShipmentPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    shipment_id: str | None = None
    client_reference: str | None = None
    outer_carrier_code: str | None = None
    outer_carrier_tracking_number: str | None = None
    status: str | None = None
    country: str | None = None
    postcode: str | None = None
    parcel_count: int | None = None
    traces: list[_TracePayload] = Field(default_factory=list)

    @field_validator(
        "shipment_id",
        "client_reference",
        "outer_carrier_code",
        "outer_carrier_tracking_number",
        "status",
        "country",
        "postcode",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value: Any) -> str | None:
        return _optional_text(value)

    @field_validator("parcel_count", mode="before")
    @classmethod
    def normalize_parcel_count(cls, value: Any) -> int | None:
        if value is None or value is False or value == "":
            return None
        return int(value)

    @field_validator("traces", mode="before")
    @classmethod
    def normalize_traces(cls, value: Any) -> Any:
        if value is None or value is False:
            return []
        return value


class _DataPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    shipment: _ShipmentPayload


class _EnvelopePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: int
    info: str = ""
    data: _DataPayload | None = None
    request_time: str | None = None
    cost_time: float | None = None


class TraceSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    time_raw: str
    info: str


class ShipmentSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    shipment_id: str | None
    client_reference: str | None
    outer_carrier_code: str | None
    outer_carrier_tracking_number: str | None
    status: str | None
    country: str | None
    postcode: str | None
    parcel_count: int | None
    traces: tuple[TraceSnapshot, ...]

    @property
    def localized_status(self) -> str:
        return status_label(self.status)


class TrackingResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    shipment: ShipmentSnapshot
    request_time: str | None
    cost_time: float | None


def parse_tracking_response(payload: Any) -> TrackingResponse:
    try:
        envelope = _EnvelopePayload.model_validate(payload)
    except ValidationError as exc:
        raise NextSlsProtocolError("NextSLS response schema is invalid") from exc

    if envelope.status != 1:
        message = envelope.info.strip() or "NextSLS rejected the tracking number"
        raise NextSlsBusinessError(message)
    if envelope.data is None:
        raise NextSlsProtocolError("NextSLS success response is missing data.shipment")

    shipment = envelope.data.shipment
    snapshot = ShipmentSnapshot(
        shipment_id=shipment.shipment_id,
        client_reference=shipment.client_reference,
        outer_carrier_code=shipment.outer_carrier_code,
        outer_carrier_tracking_number=shipment.outer_carrier_tracking_number,
        status=shipment.status,
        country=shipment.country,
        postcode=shipment.postcode,
        parcel_count=shipment.parcel_count,
        traces=tuple(
            TraceSnapshot(time_raw=trace.time, info=trace.info) for trace in shipment.traces
        ),
    )
    return TrackingResponse(
        shipment=snapshot,
        request_time=envelope.request_time,
        cost_time=envelope.cost_time,
    )


class NextSlsClient:
    def __init__(
        self,
        app_id: str,
        *,
        base_url: str = NEXTSLS_TRACKING_URL,
        timeout_seconds: float = 30.0,
        max_concurrency: int = 3,
        max_retries: int = 2,
        http_client: httpx.AsyncClient | None = None,
        sleeper: SleepCallable = asyncio.sleep,
    ) -> None:
        if not app_id.strip():
            raise ValueError("app_id must not be blank")
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be at least 1")
        if max_retries < 0:
            raise ValueError("max_retries must not be negative")

        self._app_id = app_id.strip()
        self._base_url = base_url
        self._max_retries = max_retries
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._sleeper = sleeper
        self._owns_http_client = http_client is None
        self._http_client = http_client or httpx.AsyncClient(timeout=timeout_seconds)

    async def __aenter__(self) -> NextSlsClient:
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        await self.close()

    async def close(self) -> None:
        if self._owns_http_client:
            await self._http_client.aclose()

    async def track(self, tracking_number: str) -> TrackingResponse:
        normalized_number = tracking_number.strip()
        if not normalized_number:
            raise ValueError("tracking_number must not be blank")

        async with self._semaphore:
            return await self._track_with_retries(normalized_number)

    async def _track_with_retries(self, tracking_number: str) -> TrackingResponse:
        total_attempts = self._max_retries + 1
        for attempt in range(1, total_attempts + 1):
            try:
                response = await self._http_client.get(
                    self._base_url,
                    params={"number": tracking_number, "app": self._app_id},
                )
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if attempt < total_attempts:
                    await self._sleeper(self._retry_delay(attempt))
                    continue
                raise NextSlsTransportError(
                    "NextSLS request failed after retries",
                    attempts=attempt,
                ) from exc

            if response.status_code == 429 or response.status_code >= 500:
                if attempt < total_attempts:
                    await self._sleeper(self._response_retry_delay(response, attempt))
                    continue
                raise NextSlsTransportError(
                    f"NextSLS returned HTTP {response.status_code} after retries",
                    attempts=attempt,
                    status_code=response.status_code,
                )

            if response.is_error:
                raise NextSlsTransportError(
                    f"NextSLS returned HTTP {response.status_code}",
                    attempts=attempt,
                    status_code=response.status_code,
                )

            try:
                payload = response.json()
            except ValueError as exc:
                raise NextSlsProtocolError("NextSLS returned malformed JSON") from exc
            return parse_tracking_response(payload)

        raise AssertionError("retry loop exited unexpectedly")

    @staticmethod
    def _retry_delay(attempt: int) -> float:
        return 0.5 * (2 ** (attempt - 1))

    @classmethod
    def _response_retry_delay(cls, response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after is not None:
            try:
                return max(0.0, float(retry_after))
            except ValueError:
                pass
        return cls._retry_delay(attempt)

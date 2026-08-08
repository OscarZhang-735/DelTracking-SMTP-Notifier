from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator


class CsrfResponse(BaseModel):
    csrf_token: str


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=512)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.strip()


class AdminResponse(BaseModel):
    id: int
    username: str
    csrf_token: str | None = None


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=512)
    new_password: str = Field(min_length=12, max_length=512)


class MessageResponse(BaseModel):
    message: str


class RecipientBrief(BaseModel):
    id: int
    name: str
    email: EmailStr
    enabled: bool


class TraceResponse(BaseModel):
    id: int
    time_raw: str
    info: str


class TrackingCreate(BaseModel):
    tracking_number: str = Field(min_length=1, max_length=100)
    enabled: bool = True
    notes: str | None = Field(default=None, max_length=2000)
    recipient_ids: list[int] = Field(default_factory=list)

    @field_validator("tracking_number")
    @classmethod
    def normalize_tracking_number(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("tracking number must not be blank")
        return normalized


class TrackingUpdate(BaseModel):
    tracking_number: str | None = Field(default=None, min_length=1, max_length=100)
    enabled: bool | None = None
    notes: str | None = Field(default=None, max_length=2000)
    recipient_ids: list[int] | None = None

    @field_validator("tracking_number")
    @classmethod
    def normalize_tracking_number(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("tracking number must not be blank")
        return normalized


class TrackingResponse(BaseModel):
    id: int
    tracking_number: str
    enabled: bool
    notes: str | None
    baseline_initialized: bool
    shipment_id: str | None
    client_reference: str | None
    outer_carrier_code: str | None
    outer_carrier_tracking_number: str | None
    shipment_status: str | None
    localized_status: str
    country: str | None
    postcode: str | None
    parcel_count: int | None
    last_checked_at: datetime | None
    last_success_at: datetime | None
    last_error: str | None
    recipients: list[RecipientBrief]
    traces: list[TraceResponse] = Field(default_factory=list)


class TrackingListResponse(BaseModel):
    items: list[TrackingResponse]
    total: int
    page: int
    page_size: int


class RecipientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    enabled: bool = True

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("name must not be blank")
        return normalized


class RecipientUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    email: EmailStr | None = None
    enabled: bool | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("name must not be blank")
        return normalized


class RecipientResponse(RecipientBrief):
    tracking_count: int = 0


class RecipientListResponse(BaseModel):
    items: list[RecipientResponse]
    total: int


class ScheduleSettingsRequest(BaseModel):
    enabled: bool
    interval_minutes: int = Field(ge=5, le=1440)
    timezone: str = Field(min_length=1, max_length=100)


class ScheduleSettingsResponse(ScheduleSettingsRequest):
    pass


class SmtpSettingsRequest(BaseModel):
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(ge=1, le=65535)
    security: Literal["ssl", "starttls", "none"]
    username: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, min_length=1, max_length=512)
    clear_password: bool = False
    sender_name: str = Field(min_length=1, max_length=100)
    sender_email: EmailStr

    @field_validator("host", "sender_name")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be blank")
        return normalized

    @field_validator("username")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class SmtpSettingsResponse(BaseModel):
    host: str | None
    port: int | None
    security: str | None
    username: str | None
    sender_name: str | None
    sender_email: EmailStr | None
    password_configured: bool


class TestEmailRequest(BaseModel):
    recipient_email: EmailStr


class JobRunResponse(BaseModel):
    id: int
    trigger: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    total_count: int
    success_count: int
    failure_count: int
    changed_count: int
    error_summary: str | None


class JobRunItemResponse(BaseModel):
    id: int
    tracking_item_id: int | None
    tracking_number: str
    status: str
    changed: bool
    added_event_count: int
    previous_status: str | None
    current_status: str | None
    error: str | None
    checked_at: datetime


class NotificationResponse(BaseModel):
    id: int
    recipient_email: EmailStr
    subject: str
    status: str
    attempt_count: int
    next_attempt_at: datetime | None
    last_error: str | None
    created_at: datetime
    sent_at: datetime | None


class JobRunDetailResponse(JobRunResponse):
    items: list[JobRunItemResponse]
    notifications: list[NotificationResponse]


class JobRunListResponse(BaseModel):
    items: list[JobRunResponse]
    total: int
    page: int
    page_size: int


class QueryRunResponse(BaseModel):
    job_run_id: int
    status: str
    total_count: int
    success_count: int
    failure_count: int
    changed_count: int


class RetryNotificationResponse(BaseModel):
    notification_id: int
    selected: int
    sent: int
    failed: int

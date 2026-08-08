from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_services, require_admin, require_csrf
from app.api.schemas import (
    MessageResponse,
    ScheduleSettingsRequest,
    ScheduleSettingsResponse,
    SmtpSettingsRequest,
    SmtpSettingsResponse,
    TestEmailRequest,
)
from app.models import AppSettings
from app.runtime import AppServices
from app.services.notifications import OutgoingEmail

router = APIRouter(
    prefix="/settings",
    tags=["settings"],
    dependencies=[Depends(require_admin)],
)


def get_app_settings(session: Session) -> AppSettings:
    app_settings = session.get(AppSettings, 1)
    if app_settings is None:
        raise HTTPException(status_code=500, detail="Application settings are missing")
    return app_settings


def serialize_smtp(settings: AppSettings) -> SmtpSettingsResponse:
    return SmtpSettingsResponse(
        host=settings.smtp_host,
        port=settings.smtp_port,
        security=settings.smtp_security,
        username=settings.smtp_username,
        sender_name=settings.smtp_sender_name,
        sender_email=settings.smtp_sender_email,
        password_configured=settings.smtp_password_encrypted is not None,
    )


@router.get("/schedule", response_model=ScheduleSettingsResponse)
async def get_schedule(session: Session = Depends(get_db)) -> ScheduleSettingsResponse:
    settings = get_app_settings(session)
    return ScheduleSettingsResponse(
        enabled=settings.schedule_enabled,
        interval_minutes=settings.schedule_interval_minutes,
        timezone=settings.timezone,
    )


@router.put(
    "/schedule",
    response_model=ScheduleSettingsResponse,
    dependencies=[Depends(require_csrf)],
)
async def update_schedule(
    payload: ScheduleSettingsRequest,
    services: AppServices = Depends(get_services),
    session: Session = Depends(get_db),
) -> ScheduleSettingsResponse:
    try:
        ZoneInfo(payload.timezone)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(status_code=422, detail="Unknown timezone") from exc

    settings = get_app_settings(session)
    settings.schedule_enabled = payload.enabled
    settings.schedule_interval_minutes = payload.interval_minutes
    settings.timezone = payload.timezone
    session.flush()
    services.scheduler.configure(
        interval_minutes=payload.interval_minutes,
        enabled=payload.enabled,
        timezone=payload.timezone,
    )
    return ScheduleSettingsResponse(**payload.model_dump())


@router.get("/smtp", response_model=SmtpSettingsResponse)
async def get_smtp(session: Session = Depends(get_db)) -> SmtpSettingsResponse:
    return serialize_smtp(get_app_settings(session))


@router.put(
    "/smtp",
    response_model=SmtpSettingsResponse,
    dependencies=[Depends(require_csrf)],
)
async def update_smtp(
    payload: SmtpSettingsRequest,
    services: AppServices = Depends(get_services),
    session: Session = Depends(get_db),
) -> SmtpSettingsResponse:
    if payload.password is not None and payload.clear_password:
        raise HTTPException(status_code=422, detail="Cannot set and clear password together")
    if payload.password is not None and services.smtp_cipher is None:
        raise HTTPException(status_code=503, detail="SMTP encryption key is not configured")

    settings = get_app_settings(session)
    settings.smtp_host = payload.host.strip()
    settings.smtp_port = payload.port
    settings.smtp_security = payload.security
    settings.smtp_username = payload.username.strip() if payload.username else None
    settings.smtp_sender_name = payload.sender_name.strip()
    settings.smtp_sender_email = str(payload.sender_email).lower()
    if payload.clear_password:
        settings.smtp_password_encrypted = None
    elif payload.password is not None and services.smtp_cipher is not None:
        settings.smtp_password_encrypted = services.smtp_cipher.encrypt(payload.password)
    session.flush()
    return serialize_smtp(settings)


@router.post(
    "/smtp/test",
    response_model=MessageResponse,
    dependencies=[Depends(require_csrf)],
)
async def test_smtp(
    payload: TestEmailRequest,
    services: AppServices = Depends(get_services),
    session: Session = Depends(get_db),
) -> MessageResponse:
    settings = get_app_settings(session)
    try:
        sender = services.build_email_sender(settings)
        await sender.send(
            OutgoingEmail(
                recipient_email=str(payload.recipient_email),
                subject="[DelTracking] SMTP 测试成功",
                body_text="这是一封 DelTracking SMTP 配置测试邮件。\n",
                body_html="<p>这是一封 <strong>DelTracking</strong> SMTP 配置测试邮件。</p>",
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="SMTP test failed") from exc
    return MessageResponse(message="Test email sent")

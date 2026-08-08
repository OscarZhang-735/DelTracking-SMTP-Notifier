import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, require_admin, require_csrf
from app.api.schemas import (
    AdminResponse,
    CsrfResponse,
    LoginRequest,
    MessageResponse,
    PasswordChangeRequest,
)
from app.api.security import LoginAttemptKey, LoginRateLimiter
from app.core.security import hash_password, verify_password
from app.models import Admin

router = APIRouter(prefix="/auth", tags=["authentication"])


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


@router.get("/csrf", response_model=CsrfResponse)
async def csrf(request: Request) -> CsrfResponse:
    token = request.session.get("csrf_token")
    if not isinstance(token, str):
        token = new_csrf_token()
        request.session["csrf_token"] = token
    return CsrfResponse(csrf_token=token)


@router.post(
    "/login",
    response_model=AdminResponse,
    dependencies=[Depends(require_csrf)],
)
async def login(
    payload: LoginRequest,
    request: Request,
    session: Session = Depends(get_db),
) -> AdminResponse:
    limiter: LoginRateLimiter = request.app.state.login_rate_limiter
    client_ip = request.client.host if request.client else "unknown"
    key = LoginAttemptKey(client_ip=client_ip, username=payload.username.casefold())
    if limiter.is_blocked(key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts",
        )

    admin = session.scalar(select(Admin).where(Admin.username == payload.username))
    if (
        admin is None
        or not admin.enabled
        or not verify_password(payload.password, admin.password_hash)
    ):
        limiter.record_failure(key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    limiter.clear(key)
    token = new_csrf_token()
    request.session.clear()
    request.session.update(
        {
            "admin_id": admin.id,
            "session_version": admin.session_version,
            "csrf_token": token,
        }
    )
    return AdminResponse(id=admin.id, username=admin.username, csrf_token=token)


@router.post(
    "/logout",
    response_model=MessageResponse,
    dependencies=[Depends(require_csrf)],
)
async def logout(
    request: Request,
    _admin: Admin = Depends(require_admin),
) -> MessageResponse:
    request.session.clear()
    return MessageResponse(message="Logged out")


@router.get("/me", response_model=AdminResponse)
async def me(admin: Admin = Depends(require_admin)) -> AdminResponse:
    return AdminResponse(id=admin.id, username=admin.username)


@router.put(
    "/password",
    response_model=AdminResponse,
    dependencies=[Depends(require_csrf)],
)
async def change_password(
    payload: PasswordChangeRequest,
    request: Request,
    admin: Admin = Depends(require_admin),
    session: Session = Depends(get_db),
) -> AdminResponse:
    if not verify_password(payload.current_password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    if payload.current_password == payload.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different",
        )

    admin.password_hash = hash_password(payload.new_password)
    admin.session_version += 1
    session.flush()
    token = new_csrf_token()
    request.session.update(
        {
            "session_version": admin.session_version,
            "csrf_token": token,
        }
    )
    return AdminResponse(id=admin.id, username=admin.username, csrf_token=token)

from collections.abc import Generator
from hmac import compare_digest

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.models import Admin
from app.runtime import AppServices


def get_services(request: Request) -> AppServices:
    return request.app.state.services


def get_db(services: AppServices = Depends(get_services)) -> Generator[Session]:
    with services.database.session() as session:
        yield session


def require_csrf(request: Request) -> None:
    expected = request.session.get("csrf_token")
    supplied = request.headers.get("X-CSRF-Token")
    if not expected or not supplied or not compare_digest(expected, supplied):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token is missing or invalid",
        )


def require_admin(
    request: Request,
    session: Session = Depends(get_db),
) -> Admin:
    admin_id = request.session.get("admin_id")
    session_version = request.session.get("session_version")
    if not isinstance(admin_id, int) or not isinstance(session_version, int):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    admin = session.get(Admin, admin_id)
    if admin is None or not admin.enabled or admin.session_version != session_version:
        request.session.clear()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    return admin

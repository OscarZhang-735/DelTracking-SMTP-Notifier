from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import get_db, require_admin, require_csrf
from app.api.schemas import (
    RecipientCreate,
    RecipientListResponse,
    RecipientResponse,
    RecipientUpdate,
)
from app.models import Recipient

router = APIRouter(
    prefix="/recipients",
    tags=["recipients"],
    dependencies=[Depends(require_admin)],
)


def serialize_recipient(recipient: Recipient) -> RecipientResponse:
    return RecipientResponse(
        id=recipient.id,
        name=recipient.name,
        email=recipient.email,
        enabled=recipient.enabled,
        tracking_count=len(recipient.tracking_items),
    )


@router.get("", response_model=RecipientListResponse)
async def list_recipients(session: Session = Depends(get_db)) -> RecipientListResponse:
    recipients = list(
        session.scalars(
            select(Recipient)
            .options(selectinload(Recipient.tracking_items))
            .order_by(Recipient.id)
        )
    )
    return RecipientListResponse(
        items=[serialize_recipient(item) for item in recipients],
        total=len(recipients),
    )


@router.post(
    "",
    response_model=RecipientResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def create_recipient(
    payload: RecipientCreate,
    session: Session = Depends(get_db),
) -> RecipientResponse:
    recipient = Recipient(
        name=payload.name,
        email=str(payload.email).lower(),
        enabled=payload.enabled,
    )
    session.add(recipient)
    try:
        session.flush()
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Recipient email already exists") from exc
    return serialize_recipient(recipient)


@router.patch(
    "/{recipient_id}",
    response_model=RecipientResponse,
    dependencies=[Depends(require_csrf)],
)
async def update_recipient(
    recipient_id: int,
    payload: RecipientUpdate,
    session: Session = Depends(get_db),
) -> RecipientResponse:
    recipient = session.scalar(
        select(Recipient)
        .options(selectinload(Recipient.tracking_items))
        .where(Recipient.id == recipient_id)
    )
    if recipient is None:
        raise HTTPException(status_code=404, detail="Recipient not found")
    updates = payload.model_dump(exclude_unset=True)
    if "email" in updates and updates["email"] is not None:
        updates["email"] = str(updates["email"]).lower()
    for field_name, value in updates.items():
        setattr(recipient, field_name, value)
    try:
        session.flush()
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Recipient email already exists") from exc
    return serialize_recipient(recipient)


@router.delete(
    "/{recipient_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def delete_recipient(
    recipient_id: int,
    session: Session = Depends(get_db),
) -> Response:
    recipient = session.get(Recipient, recipient_id)
    if recipient is None:
        raise HTTPException(status_code=404, detail="Recipient not found")
    session.delete(recipient)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

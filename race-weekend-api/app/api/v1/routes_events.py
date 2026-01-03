from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db.models import Event, User
from app.core.security import decode_token
from app.exceptions.handlers import AppError
from app.schemas.events import EventCreate, EventOut

router = APIRouter(prefix="/v1/events", tags=["events"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def require_user(request: Request, db: Session = Depends(get_db)) -> User:
    auth = request.headers.get("Authorization")
    if not auth or not auth.lower().startswith("bearer "):
        raise AppError("unauthorized", "Missing bearer token.", 401)

    token = auth.split(" ", 1)[1].strip()
    payload = decode_token(token)
    user = db.get(User, int(payload["sub"]))
    if not user:
        raise AppError("unauthorized", "User not found.", 401)
    request.state.user = user
    return user

def require_admin(user: User = Depends(require_user)) -> User:
    if user.role != "admin":
        raise AppError("forbidden", "Admin role required.", 403)
    return user

@router.post("", status_code=201, response_model=EventOut)
def create_event(payload: EventCreate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    event = Event(**payload.model_dump())
    db.add(event)
    db.commit()
    db.refresh(event)
    return event

@router.get("", response_model=list[EventOut])
def list_events(db: Session = Depends(get_db), _: User = Depends(require_user)):
    return db.execute(select(Event).order_by(Event.event_date)).scalars().all()

@router.get("/{event_id}", response_model=EventOut)
def get_event(event_id: int, db: Session = Depends(get_db), _: User = Depends(require_user)):
    event = db.get(Event, event_id)
    if not event:
        raise AppError("not_found", "Event not found.", 404)
    return event

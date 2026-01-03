import json
import time
from typing import Literal

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from redis import Redis
from sqlalchemy import select, asc, desc
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rate_limit import check_rate_limit
from app.core.security import decode_token
from app.db.database import SessionLocal
from app.db.models import Task, Event, User
from app.exceptions.handlers import AppError
from app.schemas.tasks import TaskCreate, TaskUpdate, TaskOut

router = APIRouter(prefix="/v1/tasks", tags=["tasks"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_redis():
    return Redis.from_url(settings.REDIS_URL, decode_responses=True)

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
    request.state.role = payload.get("role")
    return user

def apply_rate_limit_headers(response: Response, rl) -> None:
    response.headers["X-RateLimit-Limit"] = str(rl.limit)
    response.headers["X-RateLimit-Remaining"] = str(rl.remaining)
    response.headers["X-RateLimit-Reset"] = str(rl.reset)

def enforce_rate_limit(request: Request, response: Response, r: Redis) -> None:
    user: User | None = getattr(request.state, "user", None)
    key = f"user:{user.id}" if user else f"ip:{request.client.host}"

    rl = check_rate_limit(r, key)
    apply_rate_limit_headers(response, rl)

    if not rl.allowed:
        retry_after = max(0, rl.reset - int(time.time()))
        response.headers["Retry-After"] = str(retry_after)
        raise AppError("rate_limited", "Too many requests.", 429)

@router.get("", response_model=list[TaskOut])
def list_tasks(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    r: Redis = Depends(get_redis),
    _: User = Depends(require_user),
    # pagination
    skip: int = 0,
    limit: int = 20,
    # filtering
    event_id: int | None = None,
    category: str | None = None,
    completed: bool | None = None,
    priority: int | None = None,
    # sorting
    sort: Literal["id", "priority", "due_at", "title"] = "id",
    order: Literal["asc", "desc"] = "asc",
):
    enforce_rate_limit(request, response, r)
    user: User = request.state.user

    cache_key = f"cache:tasks:{user.id}:{skip}:{limit}:{event_id}:{category}:{completed}:{priority}:{sort}:{order}"
    cached = r.get(cache_key)
    if cached:
        return json.loads(cached)

    stmt = select(Task)

    # users only see tasks assigned to them OR tasks with no assignee (team-wide)
    stmt = stmt.where((Task.assignee_id == user.id) | (Task.assignee_id.is_(None)))

    if event_id is not None:
        stmt = stmt.where(Task.event_id == event_id)
    if category is not None:
        stmt = stmt.where(Task.category == category)
    if completed is not None:
        stmt = stmt.where(Task.completed == completed)
    if priority is not None:
        stmt = stmt.where(Task.priority == priority)

    ordering = asc(getattr(Task, sort)) if order == "asc" else desc(getattr(Task, sort))
    stmt = stmt.order_by(ordering).offset(skip).limit(limit)

    tasks = db.execute(stmt).scalars().all()
    data = [TaskOut.model_validate(t).model_dump() for t in tasks]

    r.setex(cache_key, settings.CACHE_TTL_SECONDS, json.dumps(data))
    return data

@router.post("", status_code=201, response_model=TaskOut)
def create_task(
    request: Request,
    response: Response,
    payload: TaskCreate,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    r: Redis = Depends(get_redis),
    _: User = Depends(require_user),
):
    enforce_rate_limit(request, response, r)
    user: User = request.state.user

    # Validate event exists
    event = db.get(Event, payload.event_id)
    if not event:
        raise AppError("bad_request", "Invalid event_id.", 400)

    # If assigning to someone else, require admin
    if payload.assignee_id is not None and payload.assignee_id != user.id:
        if user.role != "admin":
            raise AppError("forbidden", "Only admins can assign tasks to other users.", 403)

    task = Task(**payload.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)

    # background task demo: "send reminder" to assignee (simulated)
    background.add_task(_bg_log_task_created, task.id, task.title)

    # bust cache for this user (simple approach: let TTL expire; or delete wildcard keys if desired)
    return task

def _bg_log_task_created(task_id: int, title: str):
    print(f"[bg] Created task {task_id}: {title}")

@router.get("/{task_id}", response_model=TaskOut)
def get_task(
    request: Request,
    response: Response,
    task_id: int,
    db: Session = Depends(get_db),
    r: Redis = Depends(get_redis),
    _: User = Depends(require_user),
):
    enforce_rate_limit(request, response, r)
    user: User = request.state.user

    task = db.get(Task, task_id)
    if not task:
        raise AppError("not_found", "Task not found.", 404)

    # user access rule
    if task.assignee_id not in (None, user.id) and user.role != "admin":
        raise AppError("forbidden", "You do not have access to this task.", 403)

    return task

@router.patch("/{task_id}", response_model=TaskOut)
def update_task(
    request: Request,
    response: Response,
    task_id: int,
    payload: TaskUpdate,
    db: Session = Depends(get_db),
    r: Redis = Depends(get_redis),
    _: User = Depends(require_user),
):
    enforce_rate_limit(request, response, r)
    user: User = request.state.user

    task = db.get(Task, task_id)
    if not task:
        raise AppError("not_found", "Task not found.", 404)

    if task.assignee_id not in (None, user.id) and user.role != "admin":
        raise AppError("forbidden", "You do not have access to this task.", 403)

    data = payload.model_dump(exclude_unset=True)
    # assigning to another user requires admin
    if "assignee_id" in data and data["assignee_id"] not in (None, user.id) and user.role != "admin":
        raise AppError("forbidden", "Only admins can assign tasks to other users.", 403)

    for k, v in data.items():
        setattr(task, k, v)

    db.commit()
    db.refresh(task)
    return task

@router.delete("/{task_id}", status_code=204)
def delete_task(
    request: Request,
    response: Response,
    task_id: int,
    db: Session = Depends(get_db),
    r: Redis = Depends(get_redis),
    _: User = Depends(require_user),
):
    enforce_rate_limit(request, response, r)
    user: User = request.state.user

    task = db.get(Task, task_id)
    if not task:
        raise AppError("not_found", "Task not found.", 404)

    # only admin can delete unassigned/team tasks; user can delete their assigned tasks
    if task.assignee_id is None and user.role != "admin":
        raise AppError("forbidden", "Only admins can delete team-wide tasks.", 403)
    if task.assignee_id not in (None, user.id) and user.role != "admin":
        raise AppError("forbidden", "You do not have access to this task.", 403)

    db.delete(task)
    db.commit()
    return None

# --- async httpx requirement: weather for an event's track location ---
@router.get("/event/{event_id}/weather")
async def get_event_weather(
    request: Request,
    response: Response,
    event_id: int,
    db: Session = Depends(get_db),
    r: Redis = Depends(get_redis),
    _: User = Depends(require_user),
):
    enforce_rate_limit(request, response, r)

    event = db.get(Event, event_id)
    if not event:
        raise AppError("not_found", "Event not found.", 404)

    # Use Open-Meteo geocoding + forecast (no API key needed)
    async with httpx.AsyncClient(timeout=8.0) as client:
        geo = await client.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": f"{event.city}, {event.state}", "count": 1, "language": "en", "format": "json"},
        )
        if geo.status_code != 200:
            raise AppError("bad_gateway", "Geocoding provider failed.", 502)

        gj = geo.json()
        if not gj.get("results"):
            raise AppError("not_found", "Could not geocode event location.", 404)

        lat = gj["results"][0]["latitude"]
        lon = gj["results"][0]["longitude"]

        forecast = await client.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                "timezone": "auto",
            },
        )
        if forecast.status_code != 200:
            raise AppError("bad_gateway", "Weather provider failed.", 502)

    return {
        "event": {"id": event.id, "name": event.name, "track": event.track_name, "city": event.city, "state": event.state},
        "forecast": forecast.json().get("daily", {}),
    }

# --- background task endpoint (explicit) ---
@router.post("/{task_id}/remind")
def remind_task(
    request: Request,
    response: Response,
    task_id: int,
    bg: BackgroundTasks,
    db: Session = Depends(get_db),
    r: Redis = Depends(get_redis),
    _: User = Depends(require_user),
):
    enforce_rate_limit(request, response, r)

    task = db.get(Task, task_id)
    if not task:
        raise AppError("not_found", "Task not found.", 404)

    bg.add_task(_bg_send_reminder, task.id, task.title)
    return {"status": "queued", "task_id": task.id}

def _bg_send_reminder(task_id: int, title: str):
    # Replace with email/SMS/Kafka in real world.
    print(f"[bg] Reminder sent for task {task_id}: {title}")

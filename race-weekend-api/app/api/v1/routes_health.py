from fastapi import APIRouter, Depends
from redis import Redis
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import SessionLocal

router = APIRouter(prefix="/v1/health", tags=["health"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_redis():
    return Redis.from_url(settings.REDIS_URL, decode_responses=True)

@router.get("")
def health():
    return {"status": "ok"}

@router.get("/detailed")
def health_detailed(db: Session = Depends(get_db), r: Redis = Depends(get_redis)):
    db_ok = True
    redis_ok = True

    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    try:
        r.ping()
    except Exception:
        redis_ok = False

    status = "ok" if db_ok and redis_ok else "degraded"
    return {"status": status, "dependencies": {"database": db_ok, "redis": redis_ok}}

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging
from app.db.database import engine, Base
from app.exceptions.handlers import AppError, app_error_handler, unhandled_error_handler
from app.middleware.request_id import RequestIDMiddleware

from app.api.v1.routes_auth import router as auth_router
from app.api.v1.routes_events import router as events_router
from app.api.v1.routes_tasks import router as tasks_router
from app.api.v1.routes_health import router as health_router

def create_app() -> FastAPI:
    setup_logging()
    logger = logging.getLogger("app")
    logger.info("Starting %s (ENV=%s)", settings.APP_NAME, settings.ENV)

    app = FastAPI(title=settings.APP_NAME)

    # CORS (adjust origins in real deployments)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request ID middleware
    app.add_middleware(RequestIDMiddleware)

    # Exception handlers
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)

    # Routes (versioned)
    app.include_router(auth_router)
    app.include_router(events_router)
    app.include_router(tasks_router)
    app.include_router(health_router)

    @app.on_event("startup")
    def on_startup():
        # For the assignment this is fine. In real prod you’d run migrations (Alembic).
        Base.metadata.create_all(bind=engine)

    return app

app = create_app()

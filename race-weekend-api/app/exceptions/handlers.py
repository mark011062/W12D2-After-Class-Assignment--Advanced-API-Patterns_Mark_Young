from fastapi import Request
from fastapi.responses import JSONResponse
from app.schemas.errors import ErrorResponse

class AppError(Exception):
    def __init__(self, error: str, message: str, status_code: int = 400):
        self.error = error
        self.message = message
        self.status_code = status_code

async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            request_id=getattr(request.state, "request_id", None),
            error=exc.error,
            message=exc.message,
        ).model_dump(),
    )

async def unhandled_error_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            request_id=getattr(request.state, "request_id", None),
            error="internal_server_error",
            message="An unexpected error occurred.",
        ).model_dump(),
    )

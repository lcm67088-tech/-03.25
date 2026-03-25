"""
공통 예외 및 예외 핸들러
"""
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


class PlaceOptError(Exception):
    """PlaceOpt 베이스 예외"""
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(PlaceOptError):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, status_code=404)


class ConflictError(PlaceOptError):
    def __init__(self, message: str = "Resource already exists"):
        super().__init__(message, status_code=409)


class ForbiddenError(PlaceOptError):
    def __init__(self, message: str = "Access denied"):
        super().__init__(message, status_code=403)


class ValidationError(PlaceOptError):
    def __init__(self, message: str = "Validation failed"):
        super().__init__(message, status_code=422)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(PlaceOptError)
    async def placeopt_error_handler(request: Request, exc: PlaceOptError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.message},
        )

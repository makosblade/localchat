import logging
import traceback
from typing import Dict, Any, Optional, Callable
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
import httpx

# Get logger
logger = logging.getLogger("localchat")

class DetailedHTTPException(Exception):
    """Base class for HTTP exceptions with detailed error information"""
    
    def __init__(
        self, 
        status_code: int, 
        detail: str, 
        error_code: Optional[str] = None,
        error_details: Optional[Dict[str, Any]] = None
    ):
        self.status_code = status_code
        self.detail = detail
        self.error_code = error_code or f"HTTP_{status_code}"
        self.error_details = error_details or {}
        
        # Log the error
        log_data = {
            "status_code": status_code,
            "error_code": self.error_code,
            "detail": detail,
            **self.error_details
        }
        logger.error(f"HTTP Exception: {detail}", extra={"error_data": log_data})

class ModelAPIException(DetailedHTTPException):
    """Exception raised when there's an error communicating with the model API"""
    
    def __init__(
        self, 
        detail: str, 
        status_code: int = status.HTTP_502_BAD_GATEWAY,
        original_exception: Optional[Exception] = None,
        response_data: Optional[Dict[str, Any]] = None
    ):
        error_details = {"source": "model_api"}
        
        if original_exception:
            error_details["exception_type"] = type(original_exception).__name__
            
            # Add httpx specific details if available
            if isinstance(original_exception, httpx.HTTPStatusError):
                error_details["remote_status_code"] = original_exception.response.status_code
                try:
                    error_details["remote_response"] = original_exception.response.json()
                except:
                    error_details["remote_response"] = original_exception.response.text[:500]
            
        if response_data:
            error_details["response_data"] = response_data
            
        super().__init__(
            status_code=status_code,
            detail=detail,
            error_code="MODEL_API_ERROR",
            error_details=error_details
        )

class DatabaseException(DetailedHTTPException):
    """Exception raised when there's a database error"""
    
    def __init__(
        self, 
        detail: str, 
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        original_exception: Optional[Exception] = None
    ):
        error_details = {"source": "database"}
        
        if original_exception:
            error_details["exception_type"] = type(original_exception).__name__
            
        super().__init__(
            status_code=status_code,
            detail=detail,
            error_code="DATABASE_ERROR",
            error_details=error_details
        )

# Exception handlers for FastAPI
async def http_exception_handler(request: Request, exc: DetailedHTTPException) -> JSONResponse:
    """Handler for custom HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "code": exc.error_code,
            "message": exc.detail,
            "details": exc.error_details
        }
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handler for request validation errors"""
    # Extract and format validation errors
    error_details = []
    for error in exc.errors():
        error_details.append({
            "loc": error["loc"],
            "msg": error["msg"],
            "type": error["type"]
        })
    
    # Log the validation error
    logger.warning(
        f"Validation error: {len(error_details)} validation errors", 
        extra={"validation_errors": error_details}
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": True,
            "code": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "details": error_details
        }
    )

async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handler for uncaught exceptions"""
    # Get traceback information
    tb_str = traceback.format_exception(type(exc), exc, exc.__traceback__)
    
    # Log the error with traceback
    logger.error(
        f"Uncaught exception: {str(exc)}", 
        extra={"traceback": tb_str, "path": str(request.url)}
    )
    
    # Return a generic error message to the client
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": True,
            "code": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred",
            "request_id": request.state.request_id if hasattr(request.state, "request_id") else None
        }
    )

def register_exception_handlers(app) -> None:
    """Register all exception handlers with the FastAPI app"""
    app.add_exception_handler(DetailedHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(ValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

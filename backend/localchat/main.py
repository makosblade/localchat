import time
import uuid
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from .routes import router
from .error_handlers import register_exception_handlers
from .logging_config import setup_logging

# Setup logging
logger = setup_logging()

app = FastAPI(
    title="LocalChat API",
    description="API for interacting with AI models hosted at user-configured endpoints",
    version="0.1.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register custom exception handlers
register_exception_handlers(app)

# Add request ID and logging middleware
@app.middleware("http")
async def add_request_id_and_log(request: Request, call_next):
    # Generate a unique request ID
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    # Log the incoming request
    logger.info(
        f"Incoming request: {request.method} {request.url.path}",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "query_params": str(request.query_params),
            "client_ip": request.client.host,
            "user_agent": request.headers.get("user-agent", "Unknown")
        }
    )
    
    # Measure request processing time
    start_time = time.time()
    
    try:
        # Process the request
        response = await call_next(request)
        
        # Calculate processing time
        process_time = time.time() - start_time
        
        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        
        # Log the response
        logger.info(
            f"Request completed: {request.method} {request.url.path} - Status: {response.status_code}",
            extra={
                "request_id": request_id,
                "status_code": response.status_code,
                "processing_time": process_time
            }
        )
        
        return response
    except Exception as e:
        # Log any unhandled exceptions
        logger.error(
            f"Unhandled exception in request: {str(e)}",
            extra={"request_id": request_id},
            exc_info=True
        )
        
        # Return a 500 response
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": True,
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred",
                "request_id": request_id
            }
        )

# Include API routes
app.include_router(router, prefix="/api")

@app.get("/")
async def root():
    return {
        "message": "Welcome to LocalChat API",
        "docs": "/docs",
        "version": "0.1.0",
        "status": "healthy"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "timestamp": time.time()
    }

if __name__ == "__main__":
    uvicorn.run("localchat.main:app", host="0.0.0.0", port=8000, reload=True)

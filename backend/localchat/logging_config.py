import logging
import sys
from typing import Dict, Any
import json
from datetime import datetime
from pathlib import Path

# Create logs directory if it doesn't exist
logs_dir = Path("logs")
logs_dir.mkdir(exist_ok=True)

# Configure logging format
class CustomFormatter(logging.Formatter):
    """Custom formatter that includes timestamp, level, and message"""
    
    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created).isoformat()
        
        log_data: Dict[str, Any] = {
            "timestamp": timestamp,
            "level": record.levelname,
            "message": record.getMessage(),
        }
        
        # Add exception info if available
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
            
        # Add extra fields if available
        if hasattr(record, "extra"):
            log_data["extra"] = record.extra
            
        return json.dumps(log_data)

def setup_logging() -> None:
    """Configure application logging"""
    
    # Create logger
    logger = logging.getLogger("localchat")
    logger.setLevel(logging.DEBUG)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_format)
    
    # Create file handler for all logs
    file_handler = logging.FileHandler(logs_dir / "localchat.log")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(CustomFormatter())
    
    # Create file handler for errors only
    error_handler = logging.FileHandler(logs_dir / "error.log")
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(CustomFormatter())
    
    # Add handlers to logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.addHandler(error_handler)
    
    # Set propagate to False to avoid duplicate logs
    logger.propagate = False
    
    return logger

import logging
import sys
from typing import Optional

def configure_logger(name: str = "app", level: Optional[str] = None) -> logging.Logger:
    """
    Configure and return a standard logger instance.
    Uses a clean format with timestamps and log levels.
    """
    # Use generic level if not specified, defaulting to INFO
    if level is None:
        level = "INFO"
    
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    logger = logging.getLogger(name)
    logger.setLevel(numeric_level)
    
    # Check if handler already exists to avoid duplicate logs
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(numeric_level)
        
        formatter = logging.Formatter(
            '%(asctime)s | %(name)s | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
    return logger

# Create the main application logger
logger = configure_logger("zep_chat")

"""
Logging configuration and utilities.
"""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


class AsyncioCleanupFilter(logging.Filter):
    """Filter out harmless asyncio cleanup errors during shutdown.
    
    These errors are caused by the MCP client library's use of anyio task groups
    and are harmless - they occur during normal shutdown cleanup.
    """
    def filter(self, record):
        if record.name == 'asyncio' and record.levelno == logging.ERROR:
            msg = record.getMessage().lower()
            # Suppress known harmless errors during shutdown
            if any(keyword in msg for keyword in [
                'cancel scope',
                'different task',
                'unhandled exception during asyncio.run() shutdown',
                'cancelledaerror',
                'generatorexit',
                'task was entered'
            ]):
                return False
        return True


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = "scraper-prs.log",
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5,
    enable_console: bool = True,
    enable_file: bool = True,
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
) -> None:
    """
    Setup logging configuration.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (None to disable file logging)
        max_bytes: Maximum size of log file before rotation
        backup_count: Number of backup files to keep
        enable_console: Enable console logging
        enable_file: Enable file logging
        log_format: Format string for log messages
    """
    # Convert level string to logging constant
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(
        fmt=log_format,
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Console handler
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    # File handler with rotation
    if enable_file and log_file:
        # Ensure log directory exists
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8"
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # Set logging level for noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    # Add filter for asyncio to suppress harmless cleanup errors
    asyncio_logger = logging.getLogger("asyncio")
    asyncio_logger.setLevel(logging.WARNING)
    asyncio_logger.addFilter(AsyncioCleanupFilter())
    
    # Log initial message
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized at {level} level")
    if enable_file and log_file:
        logger.info(f"Log file: {log_file}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance.
    
    Args:
        name: Logger name (typically __name__)
    
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


class LogContext:
    """Context manager for temporary logging level changes."""
    
    def __init__(self, logger: logging.Logger, level: str):
        self.logger = logger
        self.new_level = getattr(logging, level.upper())
        self.old_level = None
    
    def __enter__(self):
        self.old_level = self.logger.level
        self.logger.setLevel(self.new_level)
        return self.logger
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logger.setLevel(self.old_level)

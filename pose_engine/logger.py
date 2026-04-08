"""
Logging Module for Krita 3D Pose Plugin
=======================================

Provides centralized logging with configurable verbosity levels.
Supports both console output and optional file logging for debugging.

Usage:
    from pose_engine.logger import get_logger
    
    logger = get_logger(__name__)
    logger.debug("Detailed debug information")
    logger.info("General information")
    logger.warning("Warning message")
    logger.error("Error message")
"""

import logging
import sys
from typing import Optional
from pathlib import Path


# Global logger configuration
_LOGGERS = {}
_LOG_LEVEL = logging.WARNING
_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(
    level: int = logging.WARNING,
    log_file: Optional[str] = None,
    console: bool = True
) -> None:
    """Configure global logging settings.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to log file for persistent logging
        console: Whether to output to console (default: True)
    """
    global _LOG_LEVEL
    
    _LOG_LEVEL = level
    
    # Configure root logger
    root_logger = logging.getLogger("pose_engine")
    root_logger.setLevel(level)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)
    
    # Add console handler
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    # Add file handler
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """Get or create a logger for the given module name.
    
    Args:
        name: Module name (typically __name__)
        
    Returns:
        Configured logger instance
    """
    # Ensure the name is under the pose_engine namespace
    if not name.startswith("pose_engine"):
        name = f"pose_engine.{name}"
    
    if name not in _LOGGERS:
        logger = logging.getLogger(name)
        logger.setLevel(_LOG_LEVEL)
        _LOGGERS[name] = logger
    
    return _LOGGERS[name]


def set_debug_mode(enabled: bool) -> None:
    """Enable or disable debug mode.
    
    When enabled, sets log level to DEBUG for detailed output.
    When disabled, sets log level to WARNING.
    
    Args:
        enabled: True to enable debug mode, False to disable
    """
    global _LOG_LEVEL
    
    if enabled:
        _LOG_LEVEL = logging.DEBUG
        level_name = "DEBUG"
    else:
        _LOG_LEVEL = logging.WARNING
        level_name = "WARNING"
    
    # Update all existing loggers
    for logger in _LOGGERS.values():
        logger.setLevel(_LOG_LEVEL)
    
    # Also update the root logger
    root_logger = logging.getLogger("pose_engine")
    root_logger.setLevel(_LOG_LEVEL)
    for handler in root_logger.handlers:
        handler.setLevel(_LOG_LEVEL)
    
    # Log the change
    get_logger(__name__).info(f"Log level set to {level_name}")


def log_function_call(logger: logging.Logger):
    """Decorator to log function calls with arguments.
    
    Usage:
        logger = get_logger(__name__)
        
        @log_function_call(logger)
        def my_function(arg1, arg2):
            ...
    
    Args:
        logger: Logger instance to use for logging
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger.debug(f"Calling {func.__name__}(args={args}, kwargs={kwargs})")
            try:
                result = func(*args, **kwargs)
                logger.debug(f"{func.__name__} returned: {result}")
                return result
            except Exception as e:
                logger.error(f"{func.__name__} raised {type(e).__name__}: {e}")
                raise
        return wrapper
    return decorator


class LogContext:
    """Context manager for temporary log level changes.
    
    Usage:
        with LogContext(logging.DEBUG):
            # Debug logging enabled in this block
            logger.debug("This will be shown")
    """
    
    def __init__(self, level: int):
        self._new_level = level
        self._old_level = _LOG_LEVEL
    
    def __enter__(self):
        set_debug_mode(self._new_level <= logging.DEBUG)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        set_debug_mode(self._old_level <= logging.DEBUG)
        return False


# Convenience function for quick debugging
def debug_print(*args, **kwargs):
    """Print debug message regardless of log level.
    
    Useful for quick debugging when you don't want to set up a logger.
    Prefixes output with [DEBUG] for easy identification.
    """
    print("[DEBUG]", *args, **kwargs)


# Initialize default logging
setup_logging()

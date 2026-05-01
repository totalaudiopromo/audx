"""Error handling utilities."""
import functools
import logging

logger = logging.getLogger(__name__)

def safe_operation(default_return=None, log_errors=True):
    """Decorator to wrap operations with try/except and logging."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if log_errors:
                    logger.error(f"Error in {func.__name__}: {e}", exc_info=True)
                return default_return
        return wrapper
    return decorator

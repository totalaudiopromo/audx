"""audx top-level package."""
from .ui.app import run_tui  # re-export for backward-compat CLI import

__all__ = ["run_tui"]

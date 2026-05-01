"""Logging configuration for audx."""
import logging
from pathlib import Path
from audx.config import CONFIG_DIR

def setup_logging(level=logging.INFO):
    """Configure root logger with file and console handlers."""
    log_dir = CONFIG_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    from datetime import datetime
    log_file = log_dir / f"audx-{datetime.now().strftime('%Y-%m-%d')}.log"
    
    # File handler (rotated daily by naming)
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(level)
    file_formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s')
    file_handler.setFormatter(file_formatter)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_formatter)
    
    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(file_handler)
    root.addHandler(console_handler)
    
    return root

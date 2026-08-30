# src/utils/logger.py
import logging
import sys
from pathlib import Path

from ..core.constants import LOG_DIR

def setup_logging(level=logging.INFO):
    """Setup logging configuration"""
    
    # Create logs directory
    Path(LOG_DIR).mkdir(parents=True, exist_ok=True)
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console_format = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console.setFormatter(console_format)
    root_logger.addHandler(console)
    
    # File handler
    log_file = Path(LOG_DIR) / "bot.log"
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(filename)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_format)
    root_logger.addHandler(file_handler)
    
    # Set level for noisy libraries
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    
    return root_logger

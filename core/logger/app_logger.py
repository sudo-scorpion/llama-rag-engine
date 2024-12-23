# project_root/core/logging.py
import logging
import sys
from typing import Any, Dict
from config.config import get_settings

class AppLogger:
    def __init__(self):
        self.settings = get_settings()
        self.logger = logging.getLogger("AppLogger")
        self._setup_logging()

    def _setup_logging(self) -> None:
        self.logger.setLevel(self.settings.LOG_LEVEL)
        formatter = logging.Formatter(self.settings.LOG_FORMAT)
        
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        
        file_handler = logging.FileHandler("logs/app.log")
        file_handler.setFormatter(formatter)
        
        self.logger.addHandler(stream_handler)
        self.logger.addHandler(file_handler)

    def get_logger(self, name: str) -> logging.Logger:
        return logging.getLogger(name)

logger = AppLogger().get_logger("AppLogger")
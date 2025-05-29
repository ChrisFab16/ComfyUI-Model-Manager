"""Task logging system for ComfyUI Model Manager."""

import os
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Optional

class TaskLogger:
    """Task-specific logger that writes to a dedicated file."""
    
    _instance: Optional['TaskLogger'] = None
    _logger: Optional[logging.Logger] = None
    
    def __init__(self):
        """Initialize the task logger."""
        if TaskLogger._instance is not None:
            raise RuntimeError("TaskLogger is a singleton. Use get_instance() instead.")
        
        self._setup_logger()
    
    @classmethod
    def get_instance(cls) -> 'TaskLogger':
        """Get the singleton instance of TaskLogger."""
        if cls._instance is None:
            cls._instance = TaskLogger()
        return cls._instance
    
    def _setup_logger(self):
        """Set up the logging configuration."""
        # Create logs directory if it doesn't exist
        logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs')
        os.makedirs(logs_dir, exist_ok=True)
        
        # Set up the logger
        logger = logging.getLogger('task_system')
        logger.setLevel(logging.DEBUG)
        
        # Create a rotating file handler
        log_file = os.path.join(logs_dir, 'task_system.log')
        handler = RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        
        # Create a formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - [%(task_id)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        
        # Add handler to logger
        logger.addHandler(handler)
        
        self._logger = logger
    
    def _log(self, level: int, task_id: str, message: str, **kwargs):
        """Internal method to handle logging with task context."""
        extra = {'task_id': task_id}
        self._logger.log(level, message, extra=extra, **kwargs)
    
    def debug(self, task_id: str, message: str, **kwargs):
        """Log a debug message."""
        self._log(logging.DEBUG, task_id, message, **kwargs)
    
    def info(self, task_id: str, message: str, **kwargs):
        """Log an info message."""
        self._log(logging.INFO, task_id, message, **kwargs)
    
    def warning(self, task_id: str, message: str, **kwargs):
        """Log a warning message."""
        self._log(logging.WARNING, task_id, message, **kwargs)
    
    def error(self, task_id: str, message: str, **kwargs):
        """Log an error message."""
        self._log(logging.ERROR, task_id, message, **kwargs)
    
    def task_started(self, task_id: str, task_type: str, params: dict):
        """Log task start."""
        self.info(task_id, f"Task started - Type: {task_type}, Params: {params}")
    
    def task_progress(self, task_id: str, progress: float, status: str):
        """Log task progress."""
        self.debug(task_id, f"Progress: {progress:.1f}% - Status: {status}")
    
    def task_completed(self, task_id: str, result: dict):
        """Log task completion."""
        self.info(task_id, f"Task completed - Result: {result}")
    
    def task_failed(self, task_id: str, error: str):
        """Log task failure."""
        self.error(task_id, f"Task failed - Error: {error}") 
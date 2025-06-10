"""Python package for ComfyUI Model Manager."""

import os
import sys
import json
import glob
import shutil
import folder_paths

from . import config

# Set extension URI first before other imports that depend on it
config.extension_uri = os.path.dirname(os.path.abspath(__file__))

from . import utils
from . import manager
from . import websocket_manager
from . import scan_worker
from .task_system import TaskManager
from .task_system.task_handlers import TaskHandlers

# Export key classes
from .manager import ModelManager
from .websocket_manager import WebSocketManager
from .scan_worker import ModelScanWorker

# Create necessary directories
os.makedirs(config.CACHE_ROOT, exist_ok=True)
os.makedirs(config.task_cache_uri, exist_ok=True)
os.makedirs(config.MODELS_ROOT, exist_ok=True)

# Initialize task system
TaskHandlers.get_instance()  # Initialize task handlers first
TaskManager.get_instance()  # Then initialize task manager

__all__ = ['ModelManager', 'WebSocketManager', 'ModelScanWorker', 'TaskManager'] 
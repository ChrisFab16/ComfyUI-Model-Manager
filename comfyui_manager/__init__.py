"""Python package for ComfyUI Model Manager."""

import os
import sys
import json
import glob
import shutil
import folder_paths

from . import config
from . import utils
from . import manager
from . import websocket_manager
from . import scan_worker

# Export key classes
from .manager import ModelManager
from .websocket_manager import WebSocketManager
from .scan_worker import ModelScanWorker

# Create necessary directories
os.makedirs(config.CACHE_ROOT, exist_ok=True)
os.makedirs(config.task_cache_uri, exist_ok=True)
os.makedirs(config.MODELS_ROOT, exist_ok=True)

__all__ = ['ModelManager', 'WebSocketManager', 'ModelScanWorker'] 
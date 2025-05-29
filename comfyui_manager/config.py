"""Configuration settings for the ComfyUI Model Manager plugin."""

import os

# Plugin paths
PLUGIN_ROOT = os.path.dirname(os.path.dirname(__file__))
MODELS_ROOT = os.path.join(PLUGIN_ROOT, "models")
CACHE_ROOT = os.path.join(PLUGIN_ROOT, "cache")
task_cache_uri = os.path.join(CACHE_ROOT, "tasks")  # Directory for storing task status and content files

# Model download settings
MAX_CONCURRENT_DOWNLOADS = 3
DOWNLOAD_CHUNK_SIZE = 8192  # 8KB chunks
DOWNLOAD_TIMEOUT = 30  # seconds

# Model scanning settings
SUPPORTED_MODEL_EXTENSIONS = {".ckpt", ".safetensors", ".pt", ".pth", ".bin", ".gguf"}
METADATA_FILE = "metadata.json"

# API settings
DEFAULT_API_TIMEOUT = 10  # seconds
MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds

# WebSocket settings
WS_HEARTBEAT_INTERVAL = 30  # seconds
WS_RECONNECT_DELAY = 5  # seconds

# Cache settings
CACHE_TTL = 3600  # 1 hour
MAX_CACHE_SIZE = 1024 * 1024 * 100  # 100MB

# Plugin settings
extension_tag = "ComfyUI Model Manager"
extension_uri = None

setting_key = {
    "api_key": {
        "civitai": "ModelManager.APIKey.Civitai",
        "huggingface": "ModelManager.APIKey.HuggingFace",
    },
    "download": {
        "max_task_count": "ModelManager.Download.MaxTaskCount",
    },
    "scan": {
        "include_hidden_files": "ModelManager.Scan.IncludeHiddenFiles"
    },
}

user_agent = "Mozilla/5.0 (iPad; CPU OS 12_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"


from server import PromptServer

serverInstance = PromptServer.instance
routes = serverInstance.routes

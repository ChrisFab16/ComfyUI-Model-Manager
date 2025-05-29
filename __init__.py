import os
import sys
import importlib.util

# Add the current directory to Python path
sys.path.append(os.path.dirname(__file__))

import folder_paths
from comfyui_manager import config, TaskManager, utils

# NOTE: This is an experiment
# Add .gguf extension to supported_pt_extensions
folder_paths.supported_pt_extensions.add(".gguf")

# Set up base models directory using normalized paths
comfy_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
base_models_dir = utils.normalize_path(os.path.join(comfy_root, "models"))
os.makedirs(base_models_dir, exist_ok=True)

# Initialize model type subdirectories with their extensions
model_types_config = {
    "loras": folder_paths.supported_pt_extensions,
    "checkpoints": folder_paths.supported_pt_extensions,
    "embeddings": folder_paths.supported_pt_extensions,
    "vae": folder_paths.supported_pt_extensions,
    "controlnet": folder_paths.supported_pt_extensions,
    "upscale_models": folder_paths.supported_pt_extensions,
    "clip": folder_paths.supported_pt_extensions,  # Added CLIP models
    "clip_vision": folder_paths.supported_pt_extensions  # Added CLIP Vision models
}

def register_model_path(model_type: str, model_path: str, extensions=None):
    """Helper function to register a model path with proper error handling"""
    if extensions is None:
        extensions = folder_paths.supported_pt_extensions
        
    model_path = utils.normalize_path(model_path)
    os.makedirs(model_path, exist_ok=True)
    
    if model_type not in folder_paths.folder_names_and_paths:
        folder_paths.folder_names_and_paths[model_type] = ([model_path], extensions)
    else:
        existing_paths, existing_extensions = folder_paths.folder_names_and_paths[model_type]
        if model_path not in existing_paths:
            existing_paths.append(model_path)
            # Merge extensions
            merged_extensions = existing_extensions.union(extensions) if hasattr(existing_extensions, 'union') else extensions
            folder_paths.folder_names_and_paths[model_type] = (existing_paths, merged_extensions)

# Initialize each model type directory
for model_type, extensions in model_types_config.items():
    model_path = utils.normalize_path(os.path.join(base_models_dir, model_type))
    register_model_path(model_type, model_path, extensions)

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

extension_uri = utils.normalize_path(os.path.dirname(__file__))

# TODO: Implement a smarter requirements check that:
# 1. Only runs on first install or when requirements.txt changes
# 2. Uses a hash/timestamp of requirements.txt to detect changes
# 3. Stores the last check state in a cache file
# For now, we'll skip the check to speed up startup

# # Install requirements
# requirements_path = utils.join_path(extension_uri, "requirements.txt")
# 
# with open(requirements_path, "r", encoding="utf-8") as f:
#     requirements = f.readlines()
# 
# requirements = [x.strip() for x in requirements]
# requirements = [x for x in requirements if not x.startswith("#")]
# 
# uninstalled_package = [p for p in requirements if not utils.is_installed(p)]
# 
# if len(uninstalled_package) > 0:
#     utils.print_info(f"Install dependencies...")
#     for p in uninstalled_package:
#         utils.pip_install(p)

# Init config settings
config.extension_uri = extension_uri

# Try to download web distribution
version = utils.get_current_version()
utils.download_web_distribution(version)

# Add api routes
from comfyui_manager import manager
from comfyui_manager import download
from comfyui_manager import information

routes = config.routes

manager.ModelManager().add_routes(routes)
download.ModelDownload().add_routes(routes)
information.Information().add_routes(routes)

WEB_DIRECTORY = "web"
__all__ = ["WEB_DIRECTORY", "NODE_CLASS_MAPPINGS"]

"""Utility functions for ComfyUI Model Manager."""

import os
import json
import yaml
import shutil
import tarfile
import logging
import requests
import traceback
import configparser
import functools
import mimetypes
import uuid
import glob
import platform
import pickle
from pathlib import Path
from typing import Any, Optional, Callable, Union
from datetime import datetime
import hashlib

import comfy.utils
import folder_paths

from aiohttp import web
from . import config
import aiohttp
import asyncio
from PIL import Image, ImageDraw, ImageFont


def print_info(msg, *args, **kwargs):
    logging.info(f"[{config.extension_tag}] {msg}", *args, **kwargs)


def print_warning(msg, *args, **kwargs):
    logging.warning(f"[{config.extension_tag}][WARNING] {msg}", *args, **kwargs)


def print_error(msg, *args, **kwargs):
    logging.error(f"[{config.extension_tag}] {msg}", *args, **kwargs)
    logging.debug(traceback.format_exc())


def print_debug(msg, *args, **kwargs):
    logging.debug(f"[{config.extension_tag}] {msg}", *args, **kwargs)


def normalize_path(path: str):
    return str(Path(path).as_posix())


def join_path(path: str, *paths: list[str]):
    return normalize_path(os.path.join(path, *paths))


def validate_extra_paths_config(config_data: dict) -> tuple[bool, list[str]]:
    """
    Validate the extra_model_paths.yaml configuration format.
    Returns (is_valid, list_of_errors)
    """
    errors = []
    
    if not isinstance(config_data, dict):
        return False, ["Configuration must be a dictionary/object"]
        
    valid_model_types = folder_paths.folder_names_and_paths.keys()
    
    for model_type, paths in config_data.items():
        # Check if model type is valid
        if model_type not in valid_model_types:
            errors.append(f"Invalid model type: {model_type}")
            continue
            
        # Check path format
        if isinstance(paths, str):
            if not os.path.isabs(paths):
                errors.append(f"Path for {model_type} must be absolute: {paths}")
        elif isinstance(paths, list):
            for path in paths:
                if not isinstance(path, str):
                    errors.append(f"Invalid path type for {model_type}: {type(path)}")
                elif not os.path.isabs(path):
                    errors.append(f"Path for {model_type} must be absolute: {path}")
        else:
            errors.append(f"Invalid path specification for {model_type}: must be string or list")
    
    return len(errors) == 0, errors


def resolve_model_base_paths() -> dict[str, list[str]]:
    """
    Resolve model base paths.
    Only uses paths from the root models directory and extra_model_paths.yaml
    Returns: { "checkpoints": ["path/to/checkpoints"] }
    """
    model_base_paths = {}
    
    # Get ComfyUI root directory
    comfy_root = os.path.dirname(os.path.dirname(os.path.dirname(config.PLUGIN_ROOT)))
    
    # Get base models directory
    base_models_dir = normalize_path(os.path.join(comfy_root, "models"))
    
    # Load extra paths from yaml if it exists
    extra_paths = {}
    extra_paths_file = os.path.join(comfy_root, "extra_model_paths.yaml")
    if os.path.exists(extra_paths_file):
        try:
            with open(extra_paths_file, 'r') as f:
                extra_paths = yaml.safe_load(f) or {}
                
            # Validate the configuration
            is_valid, errors = validate_extra_paths_config(extra_paths)
            if not is_valid:
                error_msg = "Invalid extra_model_paths.yaml configuration:\\n" + "\\n".join(errors)
                print_error(error_msg)
                extra_paths = {}
                
        except Exception as e:
            print_error(f"Failed to load extra_model_paths.yaml: {e}")
            extra_paths = {}
    
    # First get all paths from folder_paths
    for folder, (paths, extensions) in folder_paths.folder_names_and_paths.items():
        try:
            valid_paths = set()  # Use a set to deduplicate paths
            
            # Add paths from folder_paths
            for path in paths:
                if os.path.exists(path):
                    valid_paths.add(normalize_path(path))
            
            # Add base model path if not already included
            base_path = os.path.join(base_models_dir, folder)
            if os.path.exists(base_path):
                valid_paths.add(normalize_path(base_path))
            
            # Add extra paths if configured
            if folder in extra_paths:
                extra_folder_paths = extra_paths[folder]
                if isinstance(extra_folder_paths, list):
                    for path in extra_folder_paths:
                        if os.path.exists(path):
                            valid_paths.add(normalize_path(path))
                elif isinstance(extra_folder_paths, str) and os.path.exists(extra_folder_paths):
                    valid_paths.add(normalize_path(extra_folder_paths))
            
            # Only include folders that have valid paths
            if valid_paths:
                model_base_paths[folder] = sorted(list(valid_paths))  # Convert back to sorted list
                print_info(f"Found {len(valid_paths)} paths for {folder}: {', '.join(model_base_paths[folder])}")
                
        except Exception as e:
            print_error(f"Error resolving paths for {folder}: {str(e)}")
            continue
            
    return model_base_paths


def get_current_version():
    try:
        pyproject_path = join_path(config.extension_uri, "pyproject.toml")
        config_parser = configparser.ConfigParser()
        config_parser.read(pyproject_path)
        version = config_parser.get("project", "version")
        return version.strip("'\"")
    except:
        return "0.0.0"


def download_web_distribution(version: str):
    web_path = join_path(config.extension_uri, "web")
    dev_web_file = join_path(web_path, "manager-dev.js")
    if os.path.exists(dev_web_file):
        return

    web_version = "0.0.0"
    version_file = join_path(web_path, "version.yaml")
    if os.path.exists(version_file):
        with open(version_file, "r", encoding="utf-8", newline="") as f:
            version_content = yaml.safe_load(f)
            web_version = version_content.get("version", web_version)

    if version == web_version:
        return

    try:
        print_info(f"current version {version}, web version {web_version}")
        print_info("Downloading web distribution...")
        download_url = f"https://github.com/hayden-fr/ComfyUI-Model-Manager/releases/download/v{version}/dist.tar.gz"
        response = requests.get(download_url, stream=True)
        response.raise_for_status()

        temp_file = join_path(config.extension_uri, "temp.tar.gz")
        with open(temp_file, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        if os.path.exists(web_path):
            shutil.rmtree(web_path)

        print_info("Extracting web distribution...")
        with tarfile.open(temp_file, "r:gz") as tar:
            members = [member for member in tar.getmembers() if member.name.startswith("web/")]
            tar.extractall(path=config.extension_uri, members=members)

        os.remove(temp_file)
        print_info("Web distribution downloaded successfully.")
    except requests.exceptions.RequestException as e:
        print_error(f"Failed to download web distribution: {e}")
    except tarfile.TarError as e:
        print_error(f"Failed to extract web distribution: {e}")
    except Exception as e:
        print_error(f"An unexpected error occurred: {e}")


def is_installed(package_name: str) -> bool:
    """Check if a package is installed."""
    try:
        __import__(package_name)
        return True
    except ImportError:
        return False


def pip_install(package_name: str):
    """Install a package using pip."""
    try:
        import subprocess
        subprocess.check_call(["pip", "install", package_name])
        print_info(f"Successfully installed {package_name}")
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to install {package_name}: {e}")


def deprecated(reason: str):
    """Decorator to mark functions as deprecated."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            print_warning(f"{func.__name__} is deprecated: {reason}")
            return func(*args, **kwargs)
        return wrapper
    return decorator


def generate_uuid() -> str:
    """Generate a unique identifier."""
    return str(uuid.uuid4())


def _matches(predicate: dict):
    def _filter(obj: dict):
        return all(obj.get(key, None) == value for key, value in predicate.items())
    return _filter


def filter_with(list: list, predicate: Union[dict, Callable]):
    """Filter a list using a predicate dictionary or function."""
    if isinstance(predicate, dict):
        predicate = _matches(predicate)
    return [item for item in list if predicate(item)]


async def get_request_body(request) -> dict:
    """Get the JSON body from a request."""
    try:
        return await request.json()
    except:
        return {}


def get_model_preview_name(model_path: str) -> str:
    """Get the preview image name for a model."""
    if not os.path.exists(model_path):
        return None

    dir_name = os.path.dirname(model_path)
    base_name = os.path.splitext(os.path.basename(model_path))[0]

    # Search for preview images
    preview_patterns = [
        f"{base_name}.preview.*",
        f"{base_name}.jpg",
        f"{base_name}.jpeg",
        f"{base_name}.png",
        f"{base_name}.webp",
    ]

    for pattern in preview_patterns:
        matches = glob.glob(os.path.join(dir_name, pattern))
        if matches:
            return os.path.basename(matches[0])

    # Return default filename based on model name
    return f"{base_name}.preview.png"


def get_model_all_images(model_path: str) -> list[str]:
    """Get all preview images for a model."""
    if not os.path.exists(model_path):
        return []

    dir_name = os.path.dirname(model_path)
    base_name = os.path.splitext(os.path.basename(model_path))[0]

    # Search for preview images
    preview_patterns = [
        f"{base_name}.preview.*",
        f"{base_name}.jpg",
        f"{base_name}.jpeg",
        f"{base_name}.png",
        f"{base_name}.webp",
    ]

    images = []
    for pattern in preview_patterns:
        matches = glob.glob(os.path.join(dir_name, pattern))
        images.extend(matches)

    return images


def get_model_all_videos(model_path: str) -> list[str]:
    """Get all preview videos for a model."""
    if not os.path.exists(model_path):
        return []

    dir_name = os.path.dirname(model_path)
    base_name = os.path.splitext(os.path.basename(model_path))[0]

    # Search for preview videos
    preview_patterns = [
        f"{base_name}.preview.*",
        f"{base_name}.mp4",
        f"{base_name}.webm",
    ]

    videos = []
    for pattern in preview_patterns:
        matches = glob.glob(os.path.join(dir_name, pattern))
        for match in matches:
            content_type = resolve_file_content_type(match)
            if content_type == "video":
                videos.append(match)

    return videos


def resolve_file_content_type(filename: str) -> Optional[str]:
    """Resolve the content type of a file."""
    extension_mimetypes_cache = folder_paths.extension_mimetypes_cache
    extension = filename.split(".")[-1]
    if extension not in extension_mimetypes_cache:
        mime_type, _ = mimetypes.guess_type(filename, strict=False)
        if not mime_type:
            return None
        content_type = mime_type.split("/")[0]
        extension_mimetypes_cache[extension] = content_type
    else:
        content_type = extension_mimetypes_cache[extension]
    return content_type


def get_full_path(model_type: str, path_index: int, filename: str) -> str:
    """Get the full path for a model file.
    
    Args:
        model_type: The type of model (e.g. 'loras', 'checkpoints', etc.)
        path_index: The index of the base path to use
        filename: The name of the model file
        
    Returns:
        The full path to the model file
    """
    # Get the base path for the model type
    base_path = get_model_base_path(model_type, path_index)
    if not base_path:
        raise RuntimeError(f"Could not find base path for model type {model_type}")
    
    # Create the full path
    full_path = os.path.join(base_path, filename)
    return normalize_path(full_path)


def get_valid_full_path(model_type: str, path_index: int, filename: str) -> str:
    """
    Get the full path for a model file and validate it exists.
    
    Args:
        model_type: The type of model (e.g. 'loras', 'checkpoints')
        path_index: Index of the base path to use
        filename: Name of the model file
        
    Returns:
        Full validated path to the model file
        
    Raises:
        RuntimeError: If path is invalid or file doesn't exist
    """
    folders = resolve_model_base_paths().get(model_type, [])
    if not path_index < len(folders):
        raise RuntimeError(f"PathIndex {path_index} is not in {model_type}")
        
    base_path = folders[path_index]
    full_path = normalize_path(os.path.join(base_path, filename))
    
    if not os.path.exists(full_path):
        raise RuntimeError(f"Model file does not exist: {full_path}")
    elif os.path.islink(full_path) and not os.path.exists(os.path.realpath(full_path)):
        raise RuntimeError(f"Model path {full_path} is a broken symlink")
        
    return full_path


def get_model_base_path(model_type: str, index: int = 0) -> Optional[str]:
    """Get the base path for a model type.
    
    Args:
        model_type: The type of model (e.g. 'loras', 'checkpoints', etc.)
        index: The index of the base path to use (default: 0)
        
    Returns:
        The full path to the model type's directory, or None if invalid
    """
    # Get the paths from folder_paths
    paths = folder_paths.get_folder_paths(model_type)
    if not paths or index >= len(paths):
        # If the path doesn't exist, create it in the base models directory
        # Get the ComfyUI root directory (3 levels up from PLUGIN_ROOT)
        comfy_root = os.path.dirname(os.path.dirname(os.path.dirname(config.PLUGIN_ROOT)))
        base_models_dir = os.path.join(comfy_root, "models")
        os.makedirs(base_models_dir, exist_ok=True)
        
        type_dir = normalize_path(os.path.join(base_models_dir, model_type))
        os.makedirs(type_dir, exist_ok=True)
        
        # Add the new path to folder_paths
        if model_type not in folder_paths.folder_names_and_paths:
            folder_paths.folder_names_and_paths[model_type] = ([type_dir], folder_paths.supported_pt_extensions)
        else:
            existing_paths, extensions = folder_paths.folder_names_and_paths[model_type]
            if type_dir not in existing_paths:
                folder_paths.folder_names_and_paths[model_type] = (existing_paths + [type_dir], extensions)
        
        return type_dir
    
    return normalize_path(paths[index])


def get_download_path() -> str:
    """Get the download directory path."""
    download_path = join_path(config.PLUGIN_ROOT, "downloads")
    os.makedirs(download_path, exist_ok=True)
    return download_path


def get_model_metadata(filename: str) -> dict:
    """Get metadata for a model file.
    First tries to read from .info file, then falls back to safetensors metadata.
    Standardizes the metadata format across all sources.
    """
    metadata = {}
    
    # Try reading from .info file first
    info_file = os.path.splitext(filename)[0] + ".info"
    if os.path.exists(info_file):
        try:
            with open(info_file, "r", encoding="utf-8") as f:
                metadata = json.load(f)
        except Exception as e:
            print_error(f"Failed to load metadata from {info_file}: {e}")
    
    # If no .info file or empty metadata, try safetensors metadata
    if not metadata and filename.endswith(".safetensors"):
        try:
            out = comfy.utils.safetensors_header(filename, max_size=1024 * 1024)
            if out is not None:
                dt = json.loads(out)
                if "__metadata__" in dt:
                    metadata = dt["__metadata__"]
        except Exception as e:
            print_error(f"Failed to load safetensors metadata from {filename}: {e}")
    
    # Standardize metadata format
    standardized = {
        "name": os.path.basename(filename),
        "path": filename,
        "size": os.path.getsize(filename),
        "type": os.path.splitext(filename)[1][1:],
        "created": get_file_creation_time(filename),
        "modified": get_file_modification_time(filename),
        "hash": calculate_sha256(filename) if os.path.exists(filename) else None,
        
        # Model specific fields
        "model_type": metadata.get("model_type") or get_model_type_from_path(filename),
        "base_model": metadata.get("base_model"),
        "model_version": metadata.get("version"),
        "architecture": metadata.get("architecture"),
        
        # Training info
        "dataset": metadata.get("dataset"),
        "training_params": metadata.get("training_params"),
        "trigger_words": metadata.get("trigger_words", []),
        
        # Source info
        "source": metadata.get("source"),
        "source_url": metadata.get("source_url"),
        "license": metadata.get("license"),
        
        # Description and tags
        "name_for_display": metadata.get("name_for_display", os.path.splitext(os.path.basename(filename))[0]),
        "description": metadata.get("description", ""),
        "tags": metadata.get("tags", []),
        
        # Preview/thumbnail info
        "preview_url": metadata.get("preview_url"),
        "has_preview": bool(get_model_preview_name(filename)),
        
        # Original metadata
        "raw_metadata": metadata
    }
    
    return standardized


def get_model_type_from_path(filepath: str) -> str:
    """Determine model type from its location in the directory structure."""
    normalized = normalize_path(filepath)
    parts = normalized.split('/')
    
    # Look for standard model type directories
    model_types = {'checkpoints', 'loras', 'vae', 'clip', 'controlnet', 'diffusers'}
    for part in parts:
        if part.lower() in model_types:
            return part.lower()
    
    # Fallback to extension-based detection
    ext = os.path.splitext(filepath)[1].lower()
    if ext == '.safetensors':
        return 'checkpoints'  # Most safetensors are checkpoints
    elif ext == '.pt' or ext == '.pth':
        return 'loras'  # Most .pt files are LoRAs
    elif ext == '.ckpt':
        return 'checkpoints'
        
    return 'unknown'


def get_model_all_descriptions(model_path: str) -> list[str]:
    """Get all description files for a model."""
    if not os.path.exists(model_path):
        return []

    dir_name = os.path.dirname(model_path)
    base_name = os.path.splitext(os.path.basename(model_path))[0]

    description_patterns = [
        f"{base_name}.info",  # Prefer .info files
        f"{base_name}.txt",   # Legacy support
        f"{base_name}.md"     # Legacy support
    ]

    descriptions = []
    for pattern in description_patterns:
        matches = glob.glob(os.path.join(dir_name, pattern))
        descriptions.extend(matches)

    return descriptions


def get_model_description_name(model_path: str):
    """Get the description file name for a model, preferring .info files."""
    descriptions = get_model_all_descriptions(model_path)
    basename = os.path.splitext(os.path.basename(model_path))[0]
    
    # If we have any descriptions, prefer .info files
    if descriptions:
        info_files = [d for d in descriptions if d.endswith('.info')]
        if info_files:
            return info_files[0]
        return descriptions[0]
        
    # If no description exists, use .info extension
    return f"{basename}.info"


def save_model_description(model_path: str, content: Any):
    """Save model metadata and description to .info file."""
    if not os.path.exists(model_path):
        raise RuntimeError(f"Model not found: {model_path}")

    info_file = os.path.splitext(model_path)[0] + ".info"
    
    # Convert content to proper metadata structure
    if isinstance(content, str):
        metadata = {"description": content}
    elif isinstance(content, dict):
        metadata = content
    else:
        metadata = {"description": str(content)}
    
    # Add file information
    metadata.update({
        "name": os.path.basename(model_path),
        "path": model_path,
        "size": os.path.getsize(model_path),
        "type": os.path.splitext(model_path)[1][1:],
        "created": get_file_creation_time(model_path),
        "modified": get_file_modification_time(model_path)
    })

    try:
        # Save as JSON with proper formatting
        with open(info_file, "w", encoding="utf-8", newline="") as f:
            json.dump(metadata, f, indent=2)
            
        # Remove old .md file if it exists
        old_desc_file = os.path.splitext(model_path)[0] + ".md"
        if os.path.exists(old_desc_file):
            try:
                os.remove(old_desc_file)
            except Exception as e:
                print_error(f"Failed to remove old description file {old_desc_file}: {e}")
                
    except Exception as e:
        print_error(f"Failed to save metadata for {model_path}: {e}")
        raise


def remove_model_preview_image(model_path: str):
    """Remove all preview images for a model."""
    images = get_model_all_images(model_path)
    for image in images:
        try:
            os.remove(image)
        except Exception as e:
            print_error(f"Failed to remove preview image {image}: {e}")


def save_model_preview_image(model_path: str, image_file_or_url: Any, platform: Optional[str] = None):
    """Save a preview image for a model with optimization and validation.
    
    Args:
        model_path: Path to the model file
        image_file_or_url: Image file path, URL, or PIL Image object
        platform: Optional platform identifier (e.g. 'civitai')
    """
    if not os.path.exists(model_path):
        raise RuntimeError(f"Model not found: {model_path}")

    dir_name = os.path.dirname(model_path)
    base_name = os.path.splitext(os.path.basename(model_path))[0]
    preview_file = os.path.join(dir_name, f"{base_name}.preview.webp")  # Use WebP for better compression
    temp_file = preview_file + ".tmp"
    fallback_file = os.path.join(os.path.dirname(__file__), "assets", "no_preview.webp")

    try:
        if isinstance(image_file_or_url, str) and (image_file_or_url.startswith("http://") or image_file_or_url.startswith("https://")):
            # Download image from URL
            headers = {}
            if platform == "civitai":
                api_key = get_setting_value(None, "api_key.civitai")
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"
            
            try:
                response = requests.get(image_file_or_url, headers=headers, stream=True, timeout=30)
                response.raise_for_status()
                
                # Write to temporary file
                with open(temp_file, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
            except requests.exceptions.RequestException as e:
                print_error(f"Failed to download preview image from {image_file_or_url}: {e}")
                if os.path.exists(fallback_file):
                    import shutil
                    shutil.copy2(fallback_file, preview_file)
                return
        else:
            # Handle direct file/image input
            if isinstance(image_file_or_url, (str, bytes, Path)):
                img = Image.open(image_file_or_url)
            else:
                img = image_file_or_url
                
            # Save temporary file
            img.save(temp_file, "PNG")
            
        # Process and optimize the image
        with Image.open(temp_file) as img:
            # Validate image
            if not validate_preview_image(img):
                raise ValueError("Invalid preview image")
                
            # Convert color mode
            if img.mode in ('RGBA', 'LA'):
                background = Image.new('RGB', img.size, 'white')
                if img.mode == 'RGBA':
                    background.paste(img, mask=img.split()[3])
                else:
                    background.paste(img, mask=img.split()[1])
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
                
            # Resize if needed
            max_size = (1024, 1024)  # Maximum dimensions
            min_size = (256, 256)    # Minimum dimensions
            
            if img.width < min_size[0] or img.height < min_size[1]:
                raise ValueError(f"Image dimensions too small: {img.width}x{img.height}")
                
            if img.width > max_size[0] or img.height > max_size[1]:
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
                
            # Save optimized WebP
            img.save(preview_file, "WEBP", 
                    quality=85,  # Good quality but smaller size
                    method=6,    # Best compression
                    lossless=False,
                    exact=False)
            
            # Verify the saved file
            verify_img = Image.open(preview_file)
            verify_img.verify()
            
    except Exception as e:
        print_error(f"Failed to save preview image for {model_path}: {e}")
        if os.path.exists(fallback_file):
            import shutil
            shutil.copy2(fallback_file, preview_file)
    finally:
        # Clean up temp file
        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        except:
            pass
            
def validate_preview_image(img: Image.Image) -> bool:
    """Validate a preview image meets requirements."""
    try:
        # Check dimensions
        if img.width < 64 or img.height < 64:
            return False
            
        # Check aspect ratio
        aspect = img.width / img.height
        if aspect < 0.25 or aspect > 4.0:
            return False
            
        # Check image mode
        if img.mode not in ('RGB', 'RGBA', 'L', 'LA'):
            return False
            
        # Basic corruption check
        img.verify()
        return True
        
    except Exception as e:
        print_error(f"Image validation failed: {e}")
        return False


def rename_model(model_path: str, new_model_path: str):
    """Rename a model and all its associated files."""
    if model_path == new_model_path:
        return

    if os.path.exists(new_model_path):
        raise RuntimeError(f"Model {new_model_path} already exists")

    model_name = os.path.splitext(os.path.basename(model_path))[0]
    new_model_name = os.path.splitext(os.path.basename(new_model_path))[0]

    model_dirname = os.path.dirname(model_path)
    new_model_dirname = os.path.dirname(new_model_path)

    if not os.path.exists(new_model_dirname):
        os.makedirs(new_model_dirname)

    # Move model
    shutil.move(model_path, new_model_path)

    # Move preview
    previews = get_model_all_images(model_path)
    for preview in previews:
        preview_path = join_path(model_dirname, preview)
        preview_name = os.path.splitext(preview)[0]
        preview_ext = os.path.splitext(preview)[1]
        new_preview_path = (
            join_path(new_model_dirname, new_model_name + preview_ext)
            if preview_name == model_name
            else join_path(new_model_dirname, new_model_name + ".preview" + preview_ext)
        )
        shutil.move(preview_path, new_preview_path)

    # Move description/info files
    description = get_model_description_name(model_path)
    if description:
        description_path = join_path(model_dirname, description)
        if os.path.isfile(description_path):
            # Always use .info extension for the new file
            new_description_path = join_path(new_model_dirname, f"{new_model_name}.info")
            
            # If it's an old format (.md or .txt), convert to .info
            if not description.endswith('.info'):
                with open(description_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                save_model_description(new_model_path, content)
                os.remove(description_path)
            else:
                shutil.move(description_path, new_description_path)


def save_dict_pickle_file(filename: str, data: dict):
    """Save a dictionary to a pickle file."""
    try:
        with open(filename, "wb") as f:
            pickle.dump(data, f)
    except Exception as e:
        print_error(f"Failed to save pickle file {filename}: {e}")
        raise


def load_dict_pickle_file(filename: str) -> dict:
    """Load a dictionary from a pickle file."""
    try:
        with open(filename, "rb") as f:
            return pickle.load(f)
    except Exception as e:
        print_error(f"Failed to load pickle file {filename}: {e}")
        return {}


def resolve_setting_key(key: str) -> str:
    """Resolve a setting key to its full path."""
    parts = key.split(".")
    result = []
    for part in parts:
        if part.isdigit():
            result.append(f"[{part}]")
        else:
            if result:
                result.append(".")
            result.append(part)
    return "".join(result)


def set_setting_value(request: web.Request, key: str, value: Any):
    """Set a setting value."""
    if not hasattr(request.app, "user_settings"):
        request.app.user_settings = {}
    key = resolve_setting_key(key)
    request.app.user_settings[key] = value


def get_setting_value(request: Optional[web.Request], key: str, default: Any = None) -> Any:
    """Get a setting value."""
    if not request or not hasattr(request.app, "user_settings"):
        return default
    key = resolve_setting_key(key)
    return request.app.user_settings.get(key, default)


async def send_json(event_type: str, data: Any):
    """Send a JSON message through WebSocket with error handling."""
    try:
        from .websocket_manager import WebSocketManager
        await WebSocketManager.get_instance().broadcast(event_type, data)
    except Exception as e:
        print_error(f"Failed to send WebSocket message: {str(e)}")


def get_file_creation_time(file_path: str) -> str:
    """Get file creation time as ISO format string."""
    try:
        stat = os.stat(file_path)
        if hasattr(stat, 'st_birthtime'):  # macOS
            timestamp = stat.st_birthtime
        else:  # Linux/Windows
            timestamp = stat.st_ctime
        return datetime.fromtimestamp(timestamp).isoformat()
    except:
        return datetime.now().isoformat()


def get_file_modification_time(file_path: str) -> str:
    """Get file modification time as ISO format string."""
    try:
        timestamp = os.path.getmtime(file_path)
        return datetime.fromtimestamp(timestamp).isoformat()
    except:
        return datetime.now().isoformat()


def calculate_sha256(file_path: str) -> str:
    """Calculate SHA256 hash of a file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        SHA256 hash as a hex string
    """
    sha256_hash = hashlib.sha256()
    
    try:
        with open(file_path, "rb") as f:
            # Read the file in chunks to handle large files
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    except Exception as e:
        print_error(f"Failed to calculate hash for {file_path}: {e}")
        return ""


def generate_default_preview():
    """Generate a default no-preview image."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        
        # Create a new image with a dark background
        width, height = 512, 512
        img = Image.new('RGB', (width, height), color='#2A2A2A')
        draw = ImageDraw.Draw(img)
        
        # Draw a placeholder icon
        icon_size = 128
        icon_x = (width - icon_size) // 2
        icon_y = (height - icon_size) // 2
        
        # Draw a simple image icon
        draw.rectangle([icon_x, icon_y, icon_x + icon_size, icon_y + icon_size], outline='#666666', width=4)
        draw.line([icon_x, icon_y, icon_x + icon_size, icon_y + icon_size], fill='#666666', width=4)
        draw.line([icon_x + icon_size, icon_y, icon_x, icon_y + icon_size], fill='#666666', width=4)
        
        # Add text
        text = "No Preview Available"
        draw.text((width//2, height//2 + icon_size), text, fill='#666666', anchor="ms")
        
        # Save the image
        assets_dir = os.path.join(os.path.dirname(__file__), "assets")
        os.makedirs(assets_dir, exist_ok=True)
        preview_path = os.path.join(assets_dir, "no-preview.png")
        img.save(preview_path, "PNG")
        return preview_path
    except Exception as e:
        print_error(f"Failed to generate default preview: {e}")
        return None



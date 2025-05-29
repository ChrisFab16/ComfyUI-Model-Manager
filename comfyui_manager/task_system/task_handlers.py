"""Task handlers for different task types."""

import os
import aiohttp
import asyncio
import yaml
from typing import Dict, Any, Callable, Awaitable
from .base_task import Task, TaskStatus
from ..model_manager import ModelManager
from ..metadata_manager import MetadataManager
from ..download import ApiKey
from .. import utils, config

class TaskHandlers:
    """Handles different types of tasks."""
    
    _instance = None
    
    def __init__(self):
        """Initialize task handlers."""
        if TaskHandlers._instance is not None:
            raise RuntimeError("TaskHandlers is a singleton. Use get_instance() instead.")
        
        self._model_manager = ModelManager()
        self._metadata_manager = MetadataManager()
        self._api_key = ApiKey()
    
    @classmethod
    def get_instance(cls) -> 'TaskHandlers':
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = TaskHandlers()
        return cls._instance
    
    async def handle_download(self, task: Task) -> Dict[str, Any]:
        """Handle model download task."""
        temp_path = None
        try:
            # Get download parameters from task
            params = task.params
            url = params.get("downloadUrl")  # Changed from url to downloadUrl
            if not url:
                raise ValueError("downloadUrl parameter is required")
            
            model_type = params.get("type")  # Changed from model_type to type
            filename = params.get("filename", params.get("basename"))  # Try both filename and basename
            path_index = params.get("pathIndex", 0)  # Changed from path_index to pathIndex
            expected_size_kb = params.get("sizeKb", 0)  # Size in KB from Civitai
            
            if not model_type or not filename:
                raise ValueError("type and filename are required")
            
            # Get final path and ensure parent directory exists
            final_path = utils.get_full_path(model_type, path_index, filename)
            os.makedirs(os.path.dirname(final_path), exist_ok=True)
            
            # Check if file already exists
            if os.path.exists(final_path):
                # Get local file size in KB
                local_size_kb = os.path.getsize(final_path) / 1024
                
                # Check if metadata exists
                desc_name = utils.get_model_description_name(final_path)
                desc_path = os.path.join(os.path.dirname(final_path), desc_name) if desc_name else None
                
                # If size matches and metadata exists, mark as MODEL_EXISTS
                if abs(local_size_kb - expected_size_kb) < 1 and desc_path and os.path.exists(desc_path):  # Allow 1KB difference for rounding
                    task.status = TaskStatus.MODEL_EXISTS
                    return {
                        "success": True,
                        "file_path": final_path,
                        "size": local_size_kb * 1024,  # Convert back to bytes
                        "model_type": model_type,
                        "status": "model_exists"
                    }
                
                # Size mismatch or missing metadata, remove existing file
                try:
                    os.remove(final_path)
                    if desc_path and os.path.exists(desc_path):
                        os.remove(desc_path)
                    preview_path = utils.get_model_preview_name(final_path)
                    if preview_path:
                        preview_path = os.path.join(os.path.dirname(final_path), preview_path)
                        if os.path.exists(preview_path):
                            os.remove(preview_path)
                except Exception as e:
                    raise RuntimeError(f"Failed to remove existing incomplete file: {str(e)}")
            
            # Get download path and ensure it exists
            download_path = utils.get_download_path()
            temp_path = os.path.join(download_path, f"{task.id}.download")
            
            # Set up download
            headers = {"User-Agent": config.user_agent}
            platform = params.get("downloadPlatform")
            if platform == "civitai":
                api_key = self._api_key.get_value("civitai")
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"
            elif platform == "huggingface":
                api_key = self._api_key.get_value("huggingface")
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        raise RuntimeError(f"Download failed with status {response.status}")
                    
                    content_type = response.headers.get("content-type", "")
                    if content_type and content_type.startswith("text/html"):
                        raise RuntimeError(f"Login required to download this model. Please set up your {platform} API key.")
                    
                    total_size = int(response.headers.get('content-length', 0))
                    chunk_size = 8192
                    downloaded = 0
                    
                    with open(temp_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(chunk_size):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                if total_size > 0:
                                    task.progress = (downloaded / total_size) * 100
                                    
                                # Check if task was cancelled
                                if task.status == TaskStatus.CANCELLED:
                                    raise RuntimeError("Task was cancelled")
            
            # Move file to final location
            os.rename(temp_path, final_path)
            
            # Save description if provided
            description = params.get("description")
            if description:
                # Save description using the utility function
                utils.save_model_description(final_path, {
                    "description": description,
                    "source": platform,
                    "hash": params.get("hash"),
                    "preview": params.get("preview", [])
                })
                
                # Download preview image if available
                preview_urls = []
                try:
                    metadata = yaml.safe_load(description.split("---")[1])
                    preview_urls = metadata.get("preview", [])
                except:
                    pass
                    
                if preview_urls and len(preview_urls) > 0:
                    preview_url = preview_urls[0]
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.get(preview_url) as response:
                                if response.status == 200:
                                    preview_path = utils.get_model_preview_name(final_path)
                                    if preview_path:
                                        preview_path = os.path.join(os.path.dirname(final_path), preview_path)
                                        with open(preview_path, 'wb') as f:
                                            f.write(await response.read())
                    except:
                        pass  # Ignore preview download errors
            
            return {
                "success": True,
                "file_path": final_path,
                "size": downloaded,
                "model_type": model_type
            }
            
        except Exception as e:
            task.status = TaskStatus.ERROR
            task.error = str(e)
            # Clean up temp file if it exists
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass  # Ignore cleanup errors
            raise
    
    async def handle_scan(self, task: Task) -> Dict[str, Any]:
        """Handle model scanning task."""
        try:
            folder = task.params.get("folder")
            if not folder:
                raise ValueError("Folder parameter is required")
            
            # Start scanning with progress tracking
            total_files = 0
            processed_files = 0
            
            def progress_callback(current: int, total: int):
                nonlocal total_files, processed_files
                total_files = total
                processed_files = current
                if total_files > 0:
                    task.progress = (processed_files / total_files) * 100
            
            # Scan models
            result = await self._model_manager.scan_models(
                folder,
                progress_callback=progress_callback
            )
            
            return result
            
        except Exception as e:
            task.status = TaskStatus.ERROR
            task.error = str(e)
            raise
    
    async def handle_metadata(self, task: Task) -> Dict[str, Any]:
        """Handle metadata update task."""
        try:
            model_path = task.params.get("model_path")
            if not model_path:
                raise ValueError("Model path parameter is required")
            
            # Start metadata update with progress tracking
            def progress_callback(progress: float):
                task.progress = progress
            
            # Update metadata
            result = await self._metadata_manager.update_metadata(
                model_path,
                progress_callback=progress_callback
            )
            
            return result
            
        except Exception as e:
            task.status = TaskStatus.ERROR
            task.error = str(e)
            raise 
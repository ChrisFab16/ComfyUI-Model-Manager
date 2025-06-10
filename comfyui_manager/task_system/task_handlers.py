"""Task handlers for different task types."""

import os
import aiohttp
import asyncio
import yaml
import json
from typing import Dict, Any, Callable, Awaitable
from .base_task import Task, TaskStatus
from ..model_manager import ModelManager
from ..metadata_manager import MetadataManager
from ..download import ApiKey
from .. import utils, config
import sys
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))))
import folder_paths

class TaskHandlers:
    """Handles different types of tasks."""
    
    _instance = None
    
    def __init__(self, model_manager=None, metadata_manager=None, api_key=None):
        """Initialize task handlers."""
        if TaskHandlers._instance is not None:
            raise RuntimeError("TaskHandlers is a singleton. Use get_instance() instead.")
        
        self._model_manager = model_manager or ModelManager()
        self._metadata_manager = metadata_manager or MetadataManager()
        self._api_key = api_key or ApiKey()
        TaskHandlers._instance = self
    
    @classmethod
    def get_instance(cls) -> 'TaskHandlers':
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def _get_model_path(self, model_type: str, path_index: int = 0) -> str:
        """Get the model path for a given type and index.
        
        Args:
            model_type: The type of model (e.g. 'loras', 'checkpoints')
            path_index: The index of the path to use (default: 0)
            
        Returns:
            The path to store the model in
            
        Raises:
            ValueError: If the path index is invalid
        """
        paths = folder_paths.get_folder_paths(model_type)
        if not paths or path_index >= len(paths):
            raise ValueError(f"Invalid path index {path_index} for type {model_type}")
        return paths[path_index]
    
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
            expected_size_kb = params.get("sizeKb", 0)  # Size in KB
            
            # Get target path
            target_dir = self._get_model_path(model_type, path_index)
            target_path = os.path.join(target_dir, filename)
            
            # Check if file exists and verify size
            file_exists = os.path.exists(target_path)
            if file_exists:
                actual_size_kb = os.path.getsize(target_path) / 1024
                size_matches = abs(actual_size_kb - expected_size_kb) < 1  # Allow 1KB difference
                
                if size_matches:
                    print(f"[ComfyUI Model Manager] Model file exists with correct size: {target_path}")
                    # Update task status
                    task.status = TaskStatus.RUNNING
                    task.progress = 50  # Show progress for metadata update
                    task.message = "Updating metadata for existing model"
                    
                    # Update metadata and preview
                    await self._update_model_info(
                        task=task,
                        model_path=target_path,
                        model_info=params
                    )
                    
                    task.status = TaskStatus.COMPLETED
                    task.progress = 100
                    task.message = f"Updated metadata for existing model {filename}"
                    return {"success": True, "message": task.message}
                else:
                    print(f"[ComfyUI Model Manager] Size mismatch for {target_path}. Expected: {expected_size_kb}KB, Actual: {actual_size_kb}KB")
                    # Will re-download below
            
            # Download file
            temp_path = os.path.join(target_dir, f"{task.id}.download")
            
            # Update task status for download
            task.status = TaskStatus.RUNNING
            task.progress = 0
            task.message = f"Downloading {filename}"
            
            # Set up headers
            headers = {"User-Agent": config.user_agent}
            
            # Get API key using the same method as other parts of the codebase
            api_key = None
            if hasattr(self, '_api_key') and self._api_key:
                api_key = self._api_key.get_value("civitai")
            
            if not api_key:
                # Fallback to settings-based API key (for compatibility)
                from .. import utils
                api_key = utils.get_setting_value(None, "api_key.civitai")
            
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
                print(f"[ComfyUI Model Manager] Using Civitai API key for download authentication")
            else:
                print(f"[ComfyUI Model Manager] No Civitai API key found - download may fail for restricted models")
            
            # Download file with progress updates
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        raise RuntimeError(f"Download failed with status {response.status}")
                    
                    content_type = response.headers.get("content-type", "")
                    if content_type and content_type.startswith("text/html"):
                        raise RuntimeError("Login required to download this model. Please set up your API key.")
                    
                    total_size = int(response.headers.get('content-length', 0))
                    chunk_size = 8192
                    downloaded = 0
                    
                    with open(temp_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(chunk_size):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                
                                # Update progress
                                if total_size > 0:
                                    progress = (downloaded / total_size) * 100
                                    task.progress = progress
                                    task.message = f"Downloading {filename}: {progress:.1f}%"
                    
                    # Move file to final location
                    if os.path.exists(target_path):
                        os.remove(target_path)  # Remove existing file if it exists
                    os.rename(temp_path, target_path)
                    
                    # Update metadata and preview
                    task.progress = 95
                    task.message = "Updating metadata"
                    await self._update_model_info(
                        task=task,
                        model_path=target_path,
                        model_info=params
                    )
                    
                    # Complete task
                    task.status = TaskStatus.COMPLETED
                    task.progress = 100
                    task.message = f"Downloaded {filename} successfully"
                    return {"success": True, "message": task.message}
                    
        except Exception as e:
            # Clean up temp file if it exists
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass  # Ignore cleanup errors
            
            # Update task status
            task.status = TaskStatus.ERROR
            task.message = str(e)
            raise  # Re-raise the exception
    
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
    
    async def _download_file(self, url: str, target_path: str, expected_size_kb: int = 0) -> None:
        """Download a file from a URL to a target path.
        
        Args:
            url: The URL to download from
            target_path: The path to save the file to
            expected_size_kb: Expected file size in KB (optional)
        """
        # Ensure target directory exists
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        
        # Set up headers
        headers = {"User-Agent": config.user_agent}
        
        # Get API key using the same method as other parts of the codebase
        api_key = None
        if hasattr(self, '_api_key') and self._api_key:
            api_key = self._api_key.get_value("civitai")
        
        if not api_key:
            # Fallback to settings-based API key (for compatibility)
            from .. import utils
            api_key = utils.get_setting_value(None, "api_key.civitai")
        
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        # Download file
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    raise RuntimeError(f"Download failed with status {response.status}")
                
                content_type = response.headers.get("content-type", "")
                if content_type and content_type.startswith("text/html"):
                    raise RuntimeError("Login required to download this model. Please set up your API key.")
                
                total_size = int(response.headers.get('content-length', 0))
                chunk_size = 8192
                downloaded = 0
                
                with open(target_path, 'wb') as f:
                    async for chunk in response.content.iter_chunked(chunk_size):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            # Update progress
                            if total_size > 0:
                                progress = (downloaded / total_size) * 100
                                print(f"[ComfyUI Model Manager] Download progress: {progress:.1f}%") 
    
    async def _update_model_info(self, task: Task, model_path: str, model_info: Dict[str, Any]) -> None:
        """Update model metadata and preview."""
        try:
            # Save preview image if available
            preview_url = None
            
            # Try multiple sources for preview URL
            if model_info.get("preview_url"):
                preview_url = model_info.get("preview_url")
            elif model_info.get("preview"):
                # Handle both string and list formats
                preview = model_info.get("preview")
                if isinstance(preview, list) and preview:
                    preview_url = preview[0]
                elif isinstance(preview, str):
                    preview_url = preview
            elif model_info.get("images") and isinstance(model_info.get("images"), list):
                # Check images array
                images = model_info.get("images")
                if images:
                    preview_url = images[0] if isinstance(images[0], str) else images[0].get("url")
            else:
                # Try to extract from YAML front matter in description
                description = model_info.get("description", "")
                if description.startswith("---"):
                    try:
                        import yaml
                        yaml_end = description.find("---", 3)
                        if yaml_end > 3:
                            yaml_content = description[3:yaml_end]
                            yaml_data = yaml.safe_load(yaml_content)
                            if yaml_data and "preview" in yaml_data:
                                preview = yaml_data["preview"]
                                if isinstance(preview, list) and preview:
                                    preview_url = preview[0]
                                elif isinstance(preview, str):
                                    preview_url = preview
                    except Exception as e:
                        print(f"[ComfyUI Model Manager] Failed to parse YAML metadata: {e}")
            
            if preview_url:
                try:
                    utils.save_model_preview_image(model_path, preview_url, platform="civitai")
                    print(f"[ComfyUI Model Manager] Successfully saved preview image for {os.path.basename(model_path)} from {preview_url}")
                except Exception as e:
                    print(f"[ComfyUI Model Manager] Failed to save preview image from {preview_url}: {e}")
            else:
                print(f"[ComfyUI Model Manager] No preview URL found for {os.path.basename(model_path)}")

            # Save metadata
            info_path = model_path + ".info"
            
            # Extract structured data from the description
            description = model_info.get("description", "")
            extracted_data = self._extract_metadata_from_description(description)
            
            metadata = {
                "id": model_info.get("id") or extracted_data.get("id"),
                "modelId": model_info.get("modelId") or extracted_data.get("modelId"),
                "name": model_info.get("name") or extracted_data.get("name", ""),
                "createdAt": model_info.get("createdAt", ""),
                "updatedAt": model_info.get("updatedAt", ""),
                "trainedWords": model_info.get("trainedWords") or extracted_data.get("trainedWords", []),
                "baseModel": model_info.get("baseModel") or extracted_data.get("baseModel", ""),
                "baseModelType": model_info.get("baseModelType") or extracted_data.get("baseModelType", ""),
                "description": description,
                "model": {
                    "name": model_info.get("name") or extracted_data.get("name", ""),
                    "type": model_info.get("type", ""),
                    "nsfw": model_info.get("nsfw", False),
                    "poi": model_info.get("poi", False)
                },
                "stats": {
                    "downloadCount": model_info.get("downloadCount", 0),
                    "rating": model_info.get("rating", 0),
                    "ratingCount": model_info.get("ratingCount", 0)
                },
                "files": [{
                    "name": os.path.basename(model_path),
                    "id": model_info.get("id", ""),
                    "sizeKB": model_info.get("sizeKb", 0),
                    "type": "Model",
                    "metadata": {
                        "fp": model_info.get("fp", "fp32"),
                        "size": model_info.get("size", "full"),
                        "format": "SafeTensor" if model_path.endswith(".safetensors") else "PickleTensor"
                    },
                    "hashes": model_info.get("hashes") or extracted_data.get("hashes", {}),
                    "primary": True,
                    "downloadUrl": model_info.get("downloadUrl", "")
                }],
                "images": model_info.get("images", []),
                "downloadUrl": model_info.get("downloadUrl", ""),
                
                # Add extracted metadata for UI compatibility
                "author": extracted_data.get("author"),
                "website": extracted_data.get("website"),
                "modelPage": extracted_data.get("modelPage"),
                "trigger_words": extracted_data.get("trainedWords", []),
                "base_model": extracted_data.get("baseModel"),
                "source": extracted_data.get("website"),
                "source_url": extracted_data.get("modelPage")
            }
            with open(info_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=4)

            # Remove old .md file if it exists
            old_desc_file = os.path.splitext(model_path)[0] + ".md"
            if os.path.exists(old_desc_file):
                try:
                    os.remove(old_desc_file)
                except Exception as e:
                    print(f"[ComfyUI Model Manager] Failed to remove old description file {old_desc_file}: {e}")

        except Exception as e:
            print(f"[ComfyUI Model Manager] Failed to update model info: {e}")
            raise
    
    def _extract_metadata_from_description(self, description: str) -> dict:
        """Extract structured metadata from description with YAML front matter and trigger words."""
        extracted = {}
        
        if not description:
            return extracted
            
        try:
            # Extract YAML front matter
            if description.startswith("---"):
                import yaml
                yaml_end = description.find("---", 3)
                if yaml_end > 3:
                    yaml_content = description[3:yaml_end]
                    yaml_data = yaml.safe_load(yaml_content)
                    if yaml_data:
                        extracted.update(yaml_data)
            
            # Extract trigger words from the markdown section
            trigger_section_start = description.find("# Trigger Words")
            if trigger_section_start != -1:
                # Find the content between "# Trigger Words" and the next "# " section
                content_start = description.find("\n", trigger_section_start) + 1
                next_section = description.find("\n# ", content_start)
                
                if next_section != -1:
                    trigger_content = description[content_start:next_section].strip()
                else:
                    trigger_content = description[content_start:].strip()
                
                # Parse trigger words (comma-separated)
                if trigger_content and trigger_content != "No trigger words":
                    # Remove any empty lines and clean up
                    trigger_words = [word.strip() for word in trigger_content.replace("\n", "").split(",") if word.strip()]
                    extracted["trainedWords"] = trigger_words
                    
        except Exception as e:
            print(f"[ComfyUI Model Manager] Failed to extract metadata from description: {e}")
            
        return extracted 
import os
import uuid
import time
import requests
import base64
import aiohttp
from aiohttp import web
from typing import Union, Dict, Any, Callable, Awaitable, Literal, Optional
import asyncio
from dataclasses import dataclass
import json

import folder_paths

from . import config
from . import utils
from . import thread
from .api_key import ApiKey
from .task_system.base_task import Task, TaskStatus

class ModelDownload:
    def __init__(self):
        self.api_key = ApiKey()
        self.download_thread_pool = thread.DownloadThreadPool()
        
        # Ensure task cache directory exists
        if not os.path.exists(config.task_cache_uri):
            os.makedirs(config.task_cache_uri, exist_ok=True)

    def add_routes(self, routes):
        @routes.post("/model-manager/download/init")
        async def init_download(request):
            """Initialize download settings."""
            result = self.api_key.init(request)
            return web.json_response({"success": True, "data": result})

        @routes.post("/model-manager/download/setting")
        async def set_download_setting(request):
            """Set download settings."""
            json_data = await request.json()
            key = json_data.get("key", None)
            value = json_data.get("value", None)
            value = base64.b64decode(value).decode("utf-8") if value is not None else None
            self.api_key.set_value(key, value)
            return web.json_response({"success": True})

        @routes.get("/model-manager/download/task")
        async def scan_download_tasks(request):
            """Get list of download tasks."""
            try:
                from .task_system.task_manager import TaskManager
                task_manager = TaskManager.get_instance()
                tasks = task_manager.list_tasks()
                return web.json_response({
                    "success": True,
                    "data": [task.to_dict() for task in tasks]
                })
            except Exception as e:
                error_msg = f"Failed to get task list: {str(e)}"
                utils.print_error(error_msg)
                return web.json_response({"success": False, "error": error_msg})

        @routes.post("/model-manager/model")
        async def create_model(request):
            """Create a new model download task."""
            try:
                # Handle request JSON parsing with UTF-8 error handling
                try:
                    task_data = await request.json()
                except UnicodeDecodeError as e:
                    utils.print_error(f"UTF-8 decode error in request body: {e}")
                    return web.json_response({
                        "success": False, 
                        "error": "Request contains invalid UTF-8 data. Please check the model description for binary content."
                    })
                except ValueError as e:
                    utils.print_error(f"JSON decode error in request body: {e}")
                    return web.json_response({
                        "success": False, 
                        "error": "Invalid JSON in request body."
                    })
                
                # Create task parameters
                params = {
                    "downloadUrl": task_data.get("downloadUrl"),
                    "type": task_data.get("type"),
                    "pathIndex": task_data.get("pathIndex", 0),
                    "filename": task_data.get("filename"),
                    "downloadPlatform": task_data.get("downloadPlatform"),
                    "sizeKb": float(task_data.get("sizeKb", 0)),
                    "description": task_data.get("description"),
                    "hash": task_data.get("hash"),
                }

                # Create task through task manager
                from .task_system.task_manager import TaskManager
                task_manager = TaskManager.get_instance()
                task = await task_manager.create_task("download_model", params)
                
                # Wait for task to complete
                while task.status not in [TaskStatus.COMPLETED, TaskStatus.ERROR]:
                    await asyncio.sleep(0.1)
                
                if task.status == TaskStatus.ERROR:
                    raise RuntimeError(task.error)
                
                return web.json_response({
                    "success": True,
                    "data": {"taskId": task.id}
                })
            except Exception as e:
                error_msg = f"Failed to create download task: {str(e)}"
                utils.print_error(error_msg)
                return web.json_response({"success": False, "error": error_msg})

    async def start_download(self, task: Task):
        """Start downloading a model."""
        try:
            # Update task status
            task.status = TaskStatus.RUNNING
            
            # Get download parameters
            params = task.params
            url = params["url"]
            model_type = params["model_type"]
            path_index = params["path_index"]
            fullname = params["fullname"]
            platform = params.get("platform")
            
            # Set up temporary download path
            download_path = utils.get_download_path()
            temp_path = os.path.join(download_path, f"{task.id}.download")
            
            if not url:
                raise RuntimeError("No download URL provided")

            # Set up authentication headers
            headers = {}
            if platform == "civitai":
                api_key = self.api_key.get_value("civitai")
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"
            elif platform == "huggingface":
                api_key = self.api_key.get_value("huggingface")
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"

            # Get model path
            model_path = utils.get_full_path(model_type, path_index, fullname)
            if os.path.exists(model_path):
                raise RuntimeError(f"File already exists: {model_path}")

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 401:
                        raise RuntimeError(f"Authentication required for {platform}. Please check your API key.")
                    elif response.status == 403:
                        raise RuntimeError(f"Access denied. Your {platform} API key may have insufficient permissions.")
                    elif response.status == 404:
                        raise RuntimeError("Model file not found. It may have been moved or deleted.")
                    elif response.status != 200:
                        raise RuntimeError(f"Download failed with status {response.status}: {response.reason}")

                    # Check for HTML response (usually means auth required)
                    content_type = response.headers.get("content-type", "")
                    if "text/html" in content_type.lower():
                        raise RuntimeError(f"Authentication required for {platform}. Please set up your API key.")

                    # Get file size
                    total_size = int(response.headers.get("content-length", 0))
                    downloaded_size = 0

                    # Download to temporary file
                    with open(temp_path, "wb") as f:
                        async for chunk in response.content.iter_chunked(8192):
                            if task.status == TaskStatus.CANCELLED:
                                raise RuntimeError("Download cancelled")

                            if chunk:
                                f.write(chunk)
                                downloaded_size += len(chunk)
                                if total_size:
                                    task.progress = (downloaded_size / total_size) * 100

                    # Verify download size
                    if total_size and downloaded_size != total_size:
                        raise RuntimeError(f"Download incomplete. Expected {total_size} bytes but got {downloaded_size}")

                    # Move to final location
                    os.makedirs(os.path.dirname(model_path), exist_ok=True)
                    os.rename(temp_path, model_path)

                    # Save metadata
                    await self.save_model_metadata(params, model_path)
                    
                    # Update task status
                    task.status = TaskStatus.COMPLETED
                    task.progress = 100.0

        except Exception as e:
            # Update task status on error
            task.status = TaskStatus.ERROR
            task.error = str(e)
            
            # Clean up temp file if it exists
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
            
            # Re-raise the exception
            raise

    async def save_model_metadata(self, params: Dict[str, Any], model_path: str):
        """Save model metadata."""
        try:
            # Save preview image
            if params.get("preview_file"):
                utils.save_model_preview_image(model_path, params["preview_file"])

            # Save combined metadata and description in .info file
            info_path = model_path + ".info"
            metadata = {
                "id": params.get("id"),
                "modelId": params.get("modelId"),
                "name": params.get("name", ""),
                "createdAt": params.get("createdAt", ""),
                "updatedAt": params.get("updatedAt", ""),
                "trainedWords": params.get("trainedWords", []),
                "baseModel": params.get("baseModel", ""),
                "baseModelType": params.get("baseModelType", ""),
                "description": params.get("description", ""),
                "model": {
                    "name": params.get("name", ""),
                    "type": params.get("type", ""),
                    "nsfw": params.get("nsfw", False),
                    "poi": params.get("poi", False)
                },
                "stats": {
                    "downloadCount": params.get("downloadCount", 0),
                    "rating": params.get("rating", 0),
                    "ratingCount": params.get("ratingCount", 0)
                },
                "files": [{
                    "name": os.path.basename(model_path),
                    "id": params.get("id", ""),
                    "sizeKB": params.get("sizeKb", 0),
                    "type": "Model",
                    "metadata": {
                        "fp": params.get("fp", "fp32"),
                        "size": params.get("size", "full"),
                        "format": "SafeTensor" if model_path.endswith(".safetensors") else "PickleTensor"
                    },
                    "hashes": params.get("hashes", {}),
                    "primary": True,
                    "downloadUrl": params.get("downloadUrl", "")
                }],
                "images": params.get("images", []),
                "downloadUrl": params.get("downloadUrl", "")
            }
            with open(info_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=4)

            # Remove old .md file if it exists
            old_desc_file = os.path.splitext(model_path)[0] + ".md"
            if os.path.exists(old_desc_file):
                try:
                    os.remove(old_desc_file)
                except Exception as e:
                    utils.print_error(f"Failed to remove old description file {old_desc_file}: {e}")
        except Exception as e:
            utils.print_error(f"Failed to save metadata for {model_path}: {e}")
            raise

    async def download_complete(self):
        """
        Restore the model information from the task file
        and move the model file to the target directory.
        """
        model_type = task_content.type
        path_index = task_content.pathIndex
        fullname = task_content.fullname
        
        # Get model path
        model_path = utils.get_full_path(model_type, path_index, fullname)
        
        # Move model file
        utils.rename_model(download_tmp_file, model_path)
        
        # Save metadata in .info format
        if task_content.description:
            info_path = model_path + ".info"
            metadata = {
                "id": task_content.id if hasattr(task_content, "id") else "",
                "modelId": task_content.modelId if hasattr(task_content, "modelId") else "",
                "name": task_content.name if hasattr(task_content, "name") else "",
                "description": task_content.description,
                "model": {
                    "name": task_content.name if hasattr(task_content, "name") else "",
                    "type": task_content.type if hasattr(task_content, "type") else "",
                    "nsfw": task_content.nsfw if hasattr(task_content, "nsfw") else False,
                    "poi": task_content.poi if hasattr(task_content, "poi") else False
                },
                "stats": {
                    "downloadCount": 0,
                    "rating": 0,
                    "ratingCount": 0
                },
                "files": [{
                    "name": os.path.basename(model_path),
                    "id": task_content.id if hasattr(task_content, "id") else "",
                    "sizeKB": task_content.sizeKb if hasattr(task_content, "sizeKb") else 0,
                    "type": "Model",
                    "metadata": {
                        "format": "SafeTensor" if model_path.endswith(".safetensors") else "PickleTensor"
                    },
                    "hashes": task_content.hashes if hasattr(task_content, "hashes") else {},
                    "primary": True,
                    "downloadUrl": task_content.downloadUrl if hasattr(task_content, "downloadUrl") else ""
                }],
                "downloadUrl": task_content.downloadUrl if hasattr(task_content, "downloadUrl") else ""
            }
            with open(info_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=4)

            # Remove old .md file if it exists
            old_desc_file = os.path.splitext(model_path)[0] + ".md"
            if os.path.exists(old_desc_file):
                try:
                    os.remove(old_desc_file)
                except Exception as e:
                    utils.print_error(f"Failed to remove old description file {old_desc_file}: {e}")
        
        # Clean up task file
        time.sleep(1)
        task_file = utils.join_path(download_path, f"{task_id}.task")
        os.remove(task_file)
        await utils.send_json("complete_download_task", task_id)

    async def download_model_file(
        self,
        task_id: str,
        headers: dict,
        progress_callback: Callable[[TaskStatus], Awaitable[Any]],
        interval: float = 1.0,
    ):
        task_status = self.get_task_status(task_id)
        task_content = self.get_task_content(task_id)

        # Check download uri
        model_url = task_content.downloadUrl
        if not model_url:
            raise RuntimeError("No downloadUrl found")

        download_path = utils.get_download_path()
        download_tmp_file = utils.join_path(download_path, f"{task_id}.download")

        downloaded_size = 0
        if os.path.isfile(download_tmp_file):
            downloaded_size = os.path.getsize(download_tmp_file)
            headers["Range"] = f"bytes={downloaded_size}-"

        total_size = task_content.sizeBytes

        if total_size > 0 and downloaded_size == total_size:
            await self.download_complete()
            return

        last_update_time = time.time()
        last_downloaded_size = downloaded_size

        response = requests.get(
            url=model_url,
            headers=headers,
            stream=True,
            allow_redirects=True,
        )

        if response.status_code not in (200, 206):
            raise RuntimeError(f"Failed to download {task_content.fullname}, status code: {response.status_code}")

        # Some models require logging in before they can be downloaded.
        # If no token is carried, it will be redirected to the login page.
        content_type = response.headers.get("content-type")
        if content_type and content_type.startswith("text/html"):
            raise RuntimeError(f"{task_content.fullname} needs to be logged in to download. Please set the API-Key first.")

        # When parsing model information from HuggingFace API,
        # the file size was not found and needs to be obtained from the response header.
        # Fixed issue #169. Some model information from Civitai, providing the wrong file size
        response_total_size = float(response.headers.get("content-length", 0))
        if total_size == 0 or total_size != response_total_size:
            total_size = response_total_size
            task_content.sizeBytes = total_size

        async def update_progress():
            nonlocal last_update_time
            nonlocal last_downloaded_size
            progress = (downloaded_size / total_size) * 100 if total_size > 0 else 0
            task_status.downloadedSize = downloaded_size
            task_status.progress = progress
            task_status.bps = downloaded_size - last_downloaded_size
            await progress_callback(task_status)
            last_update_time = time.time()
            last_downloaded_size = downloaded_size
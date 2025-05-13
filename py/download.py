import os
import uuid
import time
import requests
import base64
import threading
import aiohttp
import asyncio
from typing import Callable, Awaitable, Any, Literal, Union, Optional
from dataclasses import dataclass
from aiohttp import web

import folder_paths

from . import config
from . import utils
from . import thread


@dataclass
class TaskStatus:
    taskId: str
    type: str
    fullname: str
    preview: str
    status: Literal["pause", "waiting", "doing", "cancel"] = "pause"
    platform: Optional[str] = None
    downloadedSize: float = 0
    totalSize: float = 0
    progress: float = 0
    bps: float = 0
    error: Optional[str] = None

    def __init__(self, **kwargs):
        self.taskId = kwargs.get("taskId", None)
        self.type = kwargs.get("type", None)
        self.fullname = kwargs.get("fullname", None)
        self.preview = kwargs.get("preview", None)
        self.status = kwargs.get("status", "pause")
        self.platform = kwargs.get("platform", None)
        self.downloadedSize = kwargs.get("downloadedSize", 0)
        self.totalSize = kwargs.get("totalSize", 0)
        self.progress = kwargs.get("progress", 0)
        self.bps = kwargs.get("bps", 0)
        self.error = kwargs.get("error", None)

    def to_dict(self):
        return {
            "taskId": self.taskId,
            "type": self.type,
            "fullname": self.fullname,
            "preview": self.preview,
            "status": self.status,
            "platform": self.platform,
            "downloadedSize": self.downloadedSize,
            "totalSize": self.totalSize,
            "progress": self.progress,
            "bps": self.bps,
            "error": self.error,
        }


@dataclass
class TaskContent:
    type: str
    pathIndex: int
    fullname: str
    description: str
    downloadPlatform: str
    downloadUrl: str
    sizeBytes: float
    extension: Optional[str] = None
    hashes: Optional[dict[str, str]] = None

    def __init__(self, **kwargs):
        self.type = kwargs.get("type", None)
        self.pathIndex = int(kwargs.get("pathIndex", 0))
        self.fullname = kwargs.get("fullname", None)
        self.description = kwargs.get("description", "")
        self.downloadPlatform = kwargs.get("downloadPlatform", None)
        self.downloadUrl = kwargs.get("downloadUrl", None)
        self.sizeBytes = float(kwargs.get("sizeBytes", 0))
        self.extension = kwargs.get("extension", None)
        self.hashes = kwargs.get("hashes", None)

    def to_dict(self):
        return {
            "type": self.type,
            "pathIndex": self.pathIndex,
            "fullname": self.fullname,
            "description": self.description,
            "downloadPlatform": self.downloadPlatform,
            "downloadUrl": self.downloadUrl,
            "sizeBytes": self.sizeBytes,
            "extension": self.extension,
            "hashes": self.hashes,
        }


class ApiKey:
    __store: dict[str, str] = {}
    __lock = threading.Lock()
    platforms = ["civitai", "huggingface"]  # Configurable platforms

    def __init__(self):
        self.__cache_file = os.path.join(config.extension_uri, "private.key")

    def init(self, request):
        with self.__lock:
            if not os.path.exists(self.__cache_file):
                self.__store = {
                    platform: utils.get_setting_value(request, f"api_key.{platform}")
                    for platform in self.platforms
                }
                self.__update__()
                for platform in self.platforms:
                    utils.set_setting_value(request, f"api_key.{platform}", None)
            self.__store = utils.load_dict_pickle_file(self.__cache_file)
            result: dict[str, str] = {}
            for key in self.__store:
                v = self.__store[key]
                if v is not None:
                    result[key] = v[:4] + "****" + v[-4:]
        return result

    def get_value(self, key: str):
        with self.__lock:
            return self.__store.get(key, None)

    def set_value(self, key: str, value: str):
        with self.__lock:
            if key not in self.platforms:
                raise ValueError(f"Invalid platform: {key}")
            self.__store[key] = value
            self.__update__()

    def __update__(self):
        try:
            utils.save_dict_pickle_file(self.__cache_file, self.__store)
        except Exception as e:
            utils.print_error(f"Failed to save API keys: {str(e)}")


class ModelDownload:
    def __init__(self):
        self.api_key = ApiKey()
        self.download_model_task_status: dict[str, TaskStatus] = {}
        self.download_thread_pool = thread.DownloadThreadPool()
        self.lock = threading.Lock()

    def add_routes(self, routes):
        @routes.post("/model-manager/download/init")
        async def init_download(request):
            try:
                result = self.api_key.init(request)
                return web.json_response({"success": True, "data": result})
            except Exception as e:
                error_msg = f"Failed to initialize download settings: {str(e)}"
                utils.print_error(error_msg)
                return web.json_response({"success": False, "error": error_msg})

        @routes.post("/model-manager/download/setting")
        async def set_download_setting(request):
            try:
                json_data = await request.json()
                key = json_data.get("key")
                value = json_data.get("value")
                value = base64.b64decode(value).decode("utf-8") if value else None
                self.api_key.set_value(key, value)
                return web.json_response({"success": True})
            except Exception as e:
                error_msg = f"Failed to set download setting: {str(e)}"
                utils.print_error(error_msg)
                return web.json_response({"success": False, "error": error_msg})

        @routes.get("/model-manager/download/task")
        async def scan_download_tasks(request):
            try:
                result = await self.scan_model_download_task_list()
                return web.json_response({"success": True, "data": result})
            except Exception as e:
                error_msg = f"Failed to read download task list: {str(e)}"
                utils.print_error(error_msg)
                return web.json_response({"success": False, "error": error_msg})

        @routes.get("/model-manager/download/status/{task_id}")
        async def get_download_status(request):
            try:
                task_id = request.match_info.get("task_id")
                if not task_id:
                    raise web.HTTPBadRequest(reason="Missing task ID")
                task_status = self.get_task_status(task_id)
                return web.json_response({"success": True, "data": task_status.to_dict()})
            except Exception as e:
                error_msg = f"Failed to get download status: {str(e)}"
                utils.print_error(error_msg)
                return web.json_response({"success": False, "error": error_msg})

        @routes.put("/model-manager/download/{task_id}")
        async def update_download_task(request):
            try:
                task_id = request.match_info.get("task_id")
                if not task_id:
                    raise web.HTTPBadRequest(reason="Missing task ID")
                json_data = await request.json()
                status = json_data.get("status")
                if status == "pause":
                    await self.pause_model_download_task(task_id)
                elif status == "resume":
                    await self.download_model(task_id, request)
                elif status == "cancel":
                    await self.cancel_model_download_task(task_id)
                else:
                    raise web.HTTPBadRequest(reason=f"Invalid status: {status}")
                return web.json_response({"success": True})
            except Exception as e:
                error_msg = f"Failed to update download task: {str(e)}"
                utils.print_error(error_msg)
                return web.json_response({"success": False, "error": error_msg})

        @routes.delete("/model-manager/download/{task_id}")
        async def delete_model_download_task(request):
            try:
                task_id = request.match_info.get("task_id")
                if not task_id:
                    raise web.HTTPBadRequest(reason="Missing task ID")
                await self.delete_model_download_task(task_id)
                return web.json_response({"success": True})
            except Exception as e:
                error_msg = f"Failed to delete download task: {str(e)}"
                utils.print_error(error_msg)
                return web.json_response({"success": False, "error": error_msg})

        @routes.post("/model-manager/download")
        async def create_download_task(request):
            try:
                task_data = await request.post()
                task_data = dict(task_data)
                task_id = await self.create_model_download_task(task_data, request)
                return web.json_response({"success": True, "data": {"taskId": task_id}})
            except Exception as e:
                error_msg = f"Failed to create download task: {str(e)}"
                utils.print_error(error_msg)
                return web.json_response({"success": False, "error": error_msg})

    def set_task_content(self, task_id: str, task_content: Union[TaskContent, dict]):
        with self.lock:
            download_path = utils.get_download_path()
            task_file_path = utils.join_path(download_path, f"{task_id}.task")
            try:
                utils.save_dict_pickle_file(task_file_path, task_content)
            except Exception as e:
                raise RuntimeError(f"Failed to save task content: {str(e)}") from e

    def get_task_content(self, task_id: str):
        with self.lock:
            download_path = utils.get_download_path()
            task_file = utils.join_path(download_path, f"{task_id}.task")
            if not os.path.isfile(task_file):
                raise RuntimeError(f"Task {task_id} not found")
            task_content = utils.load_dict_pickle_file(task_file)
            if isinstance(task_content, TaskContent):
                return task_content
            return TaskContent(**task_content)

    def get_task_status(self, task_id: str):
        with self.lock:
            task_status = self.download_model_task_status.get(task_id)
            if task_status is None:
                download_path = utils.get_download_path()
                task_content = self.get_task_content(task_id)
                download_file = utils.join_path(download_path, f"{task_id}.download")
                download_size = os.path.getsize(download_file) if os.path.exists(download_file) else 0
                total_size = task_content.sizeBytes
                task_status = TaskStatus(
                    taskId=task_id,
                    type=task_content.type,
                    fullname=task_content.fullname,
                    preview=utils.get_model_preview_name(download_file),
                    platform=task_content.downloadPlatform,
                    downloadedSize=download_size,
                    totalSize=total_size,
                    progress=download_size / total_size * 100 if total_size > 0 else 0,
                )
                self.download_model_task_status[task_id] = task_status
            return task_status

    def delete_task_status(self, task_id: str):
        with self.lock:
            self.download_model_task_status.pop(task_id, None)

    async def scan_model_download_task_list(self):
        with self.lock:
            download_dir = utils.get_download_path()
            task_files = [f for f in os.listdir(download_dir) if f.endswith(".task")]
            task_files.sort(key=lambda x: os.stat(os.path.join(download_dir, x)).st_ctime, reverse=True)
            task_list: list[dict] = []
            for task_file in task_files:
                task_id = task_file.replace(".task", "")
                try:
                    task_status = self.get_task_status(task_id)
                    task_list.append(task_status.to_dict())
                except Exception as e:
                    utils.print_error(f"Failed to load task {task_id}: {str(e)}")
            return task_list

    async def create_model_download_task(self, task_data: dict, request):
        valid_platforms = self.api_key.platforms
        model_type = task_data.get("type")
        path_index = task_data.get("pathIndex")
        fullname = task_data.get("fullname")
        download_platform = task_data.get("downloadPlatform")
        download_url = task_data.get("downloadUrl")
        size_bytes = task_data.get("sizeBytes", "0")
        extension = task_data.get("extension", "")

        if not model_type or model_type not in folder_paths.get_folder_paths():
            raise ValueError(f"Invalid model type: {model_type}")
        try:
            path_index = int(path_index)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid path index: {path_index}")
        if not fullname or "/" in fullname or "\\" in fullname:
            raise ValueError(f"Invalid fullname: {fullname}")
        if extension and extension.lower() not in {".safetensors", ".ckpt", ".pt", ".bin", ".pth"}:
            raise ValueError(f"Invalid extension: {extension}")
        if download_platform not in valid_platforms:
            raise ValueError(f"Invalid download platform: {download_platform}")
        if not download_url or not download_url.startswith(("http://", "https://")):
            raise ValueError(f"Invalid download URL: {download_url}")
        try:
            size_bytes = float(size_bytes) if size_bytes else 0
        except (TypeError, ValueError):
            size_bytes = 0

        model_path = utils.get_full_path(model_type, path_index, fullname)
        if os.path.exists(model_path):
            raise RuntimeError(f"Model already exists: {model_path}")

        download_path = utils.get_download_path()
        task_id = uuid.uuid4().hex
        task_path = utils.join_path(download_path, f"{task_id}.task")
        if os.path.exists(task_path):
            raise RuntimeError(f"Task {task_id} already exists")

        try:
            preview_file = task_data.pop("previewFile", None)
            if preview_file and not isinstance(preview_file, (str, bytes)):
                utils.save_model_preview_image(task_path, preview_file, download_platform)
            task_data["sizeBytes"] = size_bytes
            task_data["extension"] = extension
            self.set_task_content(task_id, task_data)
            task_status = TaskStatus(
                taskId=task_id,
                type=model_type,
                fullname=fullname,
                preview=utils.get_model_preview_name(task_path),
                platform=download_platform,
                totalSize=size_bytes,
            )
            with self.lock:
                self.download_model_task_status[task_id] = task_status
            await utils.send_json("create_download_task", task_status.to_dict())
        except Exception as e:
            await self.delete_model_download_task(task_id)
            raise RuntimeError(f"Failed to create task: {str(e)}") from e

        await self.download_model(task_id, request)
        return task_id

    async def pause_model_download_task(self, task_id: str):
        task_status = self.get_task_status(task_id)
        task_status.status = "pause"
        await utils.send_json("update_download_task", task_status.to_dict())

    async def cancel_model_download_task(self, task_id: str):
        task_status = self.get_task_status(task_id)
        task_status.status = "cancel"
        await utils.send_json("update_download_task", task_status.to_dict())
        await self.delete_model_download_task(task_id)

    async def delete_model_download_task(self, task_id: str):
        task_status = self.get_task_status(task_id)
        is_running = task_status.status == "doing"
        task_status.status = "waiting"
        await utils.send_json("delete_download_task", task_id)
        if is_running:
            task_status.status = "pause"
            await asyncio.sleep(1)
        with self.lock:
            download_dir = utils.get_download_path()
            try:
                for task_file in os.listdir(download_dir):
                    if os.path.splitext(task_file)[0] == task_id:
                        os.remove(os.path.join(download_dir, task_file))
                self.delete_task_status(task_id)
            except Exception as e:
                utils.print_error(f"Failed to delete task files for {task_id}: {str(e)}")
        await utils.send_json("delete_download_task", task_id)

    async def download_model(self, task_id: str, request):
        async def download_task(task_id: str):
            async def report_progress(task_status: TaskStatus):
                await utils.send_json("update_download_task", task_status.to_dict())

            try:
                task_status = self.get_task_status(task_id)
            except Exception as e:
                await utils.send_json("error_download_task", {"taskId": task_id, "error": str(e)})
                return
            task_status.status = "doing"
            await utils.send_json("update_download_task", task_status.to_dict())
            try:
                headers = {"User-Agent": config.user_agent}
                download_platform = task_status.platform
                if download_platform:
                    api_key = self.api_key.get_value(download_platform)
                    if api_key:
                        headers["Authorization"] = f"Bearer {api_key}"
                await self.download_model_file(
                    task_id=task_id,
                    headers=headers,
                    progress_callback=report_progress,
                    interval=1.0,  # Throttle updates
                )
            except Exception as e:
                task_status.status = "pause"
                task_status.error = str(e)
                await utils.send_json("error_download_task", {"taskId": task_id, "error": str(e)})
                task_status.error = None
                utils.print_error(str(e))

        try:
            status = self.download_thread_pool.submit(download_task, task_id)
            if status == "Waiting":
                task_status = self.get_task_status(task_id)
                task_status.status = "waiting"
                await utils.send_json("update_download_task", task_status.to_dict())
        except Exception as e:
            task_status = self.get_task_status(task_id)
            task_status.status = "pause"
            task_status.error = str(e)
            await utils.send_json("error_download_task", {"taskId": task_id, "error": str(e)})
            task_status.error = None
            utils.print_error(str(e))

    async def download_model_file(
        self,
        task_id: str,
        headers: dict,
        progress_callback: Callable[[TaskStatus], Awaitable[Any]],
        interval: float = 1.0,
    ):
        async def download_complete():
            model_type = task_content.type
            path_index = task_content.pathIndex
            fullname = task_content.fullname
            description = task_content.description
            model_path = utils.get_full_path(model_type, path_index, fullname)
            try:
                if description:
                    description_file = os.path.join(download_path, f"{task_id}.md")
                    with open(description_file, "w", encoding="utf-8", newline="") as f:
                        f.write(description)
                utils.rename_model(download_tmp_file, model_path)
                task_file = os.path.join(download_path, f"{task_id}.task")
                os.remove(task_file)
                await utils.send_json("complete_download_task", task_id)  # Send only task_id
            except Exception as e:
                raise RuntimeError(f"Failed to complete download: {str(e)}") from e

        async def update_progress():
            nonlocal last_update_time, last_downloaded_size
            progress = (downloaded_size / total_size) * 100 if total_size > 0 else 0
            task_status.downloadedSize = downloaded_size
            task_status.progress = progress
            task_status.bps = downloaded_size - last_downloaded_size
            await progress_callback(task_status)
            last_update_time = time.time()
            last_downloaded_size = downloaded_size

        task_status = self.get_task_status(task_id)
        task_content = self.get_task_content(task_id)
        model_url = task_content.downloadUrl
        if not model_url:
            raise RuntimeError("No download URL provided")
        download_path = utils.get_download_path()
        download_tmp_file = os.path.join(download_path, f"{task_id}.download")
        downloaded_size = os.path.getsize(download_tmp_file) if os.path.isfile(download_tmp_file) else 0
        total_size = task_content.sizeBytes
        if total_size > 0 and downloaded_size >= total_size:
            await download_complete()
            return
        last_update_time = time.time()
        last_downloaded_size = downloaded_size
        headers = headers.copy()
        if downloaded_size > 0:
            headers["Range"] = f"bytes={downloaded_size}-"

        async with aiohttp.ClientSession() as session:
            async with session.get(model_url, headers=headers) as response:
                if response.status not in (200, 206):
                    raise RuntimeError(f"Failed to download {task_content.fullname}, status: {response.status}")
                content_type = response.headers.get("content-type")
                if content_type and content_type.startswith("text/html"):
                    raise RuntimeError(f"{task_content.fullname} requires login. Please set the API key for {task_content.downloadPlatform} in settings.")
                response_total_size = float(response.headers.get("content-length", 0))
                if total_size == 0 or total_size != response_total_size:
                    total_size = response_total_size
                    task_content.sizeBytes = total_size
                    task_status.totalSize = total_size
                    self.set_task_content(task_id, task_content)
                    await utils.send_json("update_download_task", task_content.to_dict())
                with open(download_tmp_file, "ab") as f:
                    async for chunk in response.content.iter_chunked(8192):
                        if task_status.status in ("pause", "cancel"):
                            break
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        if time.time() - last_update_time >= interval:
                            await update_progress()
                await update_progress()
                if total_size > 0 and downloaded_size >= total_size:
                    await download_complete()
                else:
                    task_status.status = "pause"
                    await utils.send_json("update_download_task", task_status.to_dict())

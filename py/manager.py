import os
import folder_paths
from concurrent.futures import ThreadPoolExecutor, as_completed
from aiohttp import web
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from . import utils
import logging
import asyncio
import threading
import functools

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info("ModelManager: Initializing extension")  # Debug log

app = FastAPI()  # FastAPI instance
web_dir = os.path.join(os.path.dirname(__file__), "..", "web")  # Absolute path to web/
app.mount("/model-manager", StaticFiles(directory=web_dir), name="model-manager")  # Mount web/ folder

class ModelManager:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.lock = asyncio.Lock()  # Use async lock instead of threading lock
        self.running_tasks = {}  # task_id -> {status, results, error}
        self._shutdown = False

    def add_routes(self, routes):
        @routes.get("/model-manager/base-folders")
        @utils.deprecated(reason="Use `/model-manager/models` instead.")
        async def get_model_paths(request):
            model_base_paths = utils.resolve_model_base_paths()
            return web.json_response({"success": True, "data": model_base_paths})

        @routes.get("/model-manager/models")
        async def get_folders(request):
            try:
                result = utils.resolve_model_base_paths()
                logger.info(f"Returning folders: {result}")
                return web.json_response({"success": True, "data": result})
            except Exception as e:
                error_msg = f"Read models failed: {str(e)}"
                utils.print_error(error_msg)
                return web.json_response({"success": False, "error": error_msg})

        @routes.get("/model-manager/scan/start")
        async def start_scan(request):
            folder = request.query.get("folder", None)
            if not folder:
                return web.json_response({"success": False, "error": "Folder parameter is required"})
            
            task_id = f"scan_{folder}_{id(request)}"
            async with self.lock:
                if task_id in self.running_tasks:
                    return web.json_response({"success": True, "task_id": task_id, "status": "running"})

                self.running_tasks[task_id] = {"status": "running", "results": [], "error": None}

            # Create scan task properly without blocking
            asyncio.create_task(self._run_scan_task(folder, request, task_id))
            return web.json_response({"success": True, "task_id": task_id, "status": "started"})

        @routes.get("/model-manager/scan/status/{task_id}")
        async def get_scan_status(request):
            task_id = request.match_info.get("task_id", None)
            async with self.lock:
                task = self.running_tasks.get(task_id, {"status": "not_found", "results": [], "error": None})
            return web.json_response({"success": True, "status": task["status"], "data": task["results"], "error": task["error"]})

        @routes.get("/model-manager/models/{folder}")
        async def get_folder_models(request):
            try:
                folder = request.match_info.get("folder", None)
                results = await self.scan_models(folder, request)
                return web.json_response({"success": True, "data": results})
            except Exception as e:
                error_msg = f"Read models failed: {str(e)}"
                utils.print_error(error_msg)
                return web.json_response({"success": False, "error": error_msg})

        @routes.get("/model-manager/model/{type}/{index}/{filename:.*}")
        async def get_model_info(request):
            model_type = request.match_info.get("type", None)
            path_index = int(request.match_info.get("index", None))
            filename = request.match_info.get("filename", None)

            try:
                model_type = model_type + 's' if model_type == 'checkpoint' else model_type
                model_path = utils.get_valid_full_path(model_type, path_index, filename)
                logger.info(f"Get model info - Type: {model_type}, PathIndex: {path_index}, Filename: {filename}, Path: {model_path}")
                if model_path is None:
                    raise RuntimeError(f"File {filename} not found")
                
                # Run blocking I/O in executor to prevent UI blocking
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(self.executor, self.get_model_info, model_path)
                return web.json_response({"success": True, "data": result})
            except Exception as e:
                error_msg = f"Read model info failed: {str(e)}"
                utils.print_error(error_msg)
                return web.json_response({"success": False, "error": error_msg})

        @routes.put("/model-manager/model/{type}/{index}/{filename:.*}")
        async def update_model(request):
            model_type = request.match_info.get("type", None)
            path_index = int(request.match_info.get("index", None))
            filename = request.match_info.get("filename", None)

            model_type = model_type + 's' if model_type == 'checkpoint' else model_type
            logger.info(f"Update model - Type: {model_type}, PathIndex: {path_index}, Filename: {filename}")

            model_data = await request.post()
            model_data = dict(model_data)

            try:
                model_path = utils.get_valid_full_path(model_type, path_index, filename)
                logger.info(f"Model path resolved: {model_path}")
                if model_path is None:
                    raise RuntimeError(f"File {filename} not found at index {path_index} for type {model_type}")
                
                # Run blocking I/O in executor
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(self.executor, self.update_model, model_path, model_data)
                return web.json_response({"success": True})
            except Exception as e:
                error_msg = f"Update model failed: {str(e)}"
                utils.print_error(error_msg)
                return web.json_response({"success": False, "error": error_msg})

        @routes.delete("/model-manager/model/{type}/{index}/{filename:.*}")
        async def delete_model(request):
            model_type = request.match_info.get("type", None)
            path_index = int(request.match_info.get("index", None))
            filename = request.match_info.get("filename", None)

            model_type = model_type + 's' if model_type == 'checkpoint' else model_type
            logger.info(f"Delete model - Type: {model_type}, PathIndex: {path_index}, Filename: {filename}")

            try:
                model_path = utils.get_valid_full_path(model_type, path_index, filename)
                logger.info(f"Model path resolved: {model_path}")
                if model_path is None:
                    raise RuntimeError(f"File {filename} not found at index {path_index} for type {model_type}")
                
                # Run blocking I/O in executor
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(self.executor, self.remove_model, model_path)
                return web.json_response({"success": True})
            except Exception as e:
                error_msg = f"Delete model failed: {str(e)}"
                utils.print_error(error_msg)
                return web.json_response({"success": False, "error": error_msg})

        @routes.get("/model-manager/download/status")
        async def get_download_tasks(request):
            async with self.lock:
                tasks = [
                    {
                        "taskId": task_id,
                        "status": task["status"],
                        "fullname": task["results"].get("fullname", "Unknown") if task["results"] else "Unknown",
                        "downloadedSize": task["results"].get("downloadedSize", 0) if task["results"] else 0,
                        "totalSize": task["results"].get("totalSize", 0) if task["results"] else 0,
                        "bps": task["results"].get("bps", 0) if task["results"] else 0,
                        "error": task["error"],
                    }
                    for task_id, task in self.running_tasks.items()
                    if task_id.startswith("download_")
                ]
            return web.json_response({"success": True, "data": tasks})

        @routes.post("/model-manager/download")
        async def download_model(request):
            try:
                model_data = await request.post()
                model_data = dict(model_data)

                model_type = model_data.get("type")
                path_index = model_data.get("pathIndex")
                fullname = model_data.get("fullname")
                url = model_data.get("url")

                if not model_type:
                    raise ValueError("Model type is required")
                model_type = model_type + 's' if model_type == 'checkpoint' else model_type
                if model_type not in folder_paths.folder_names_and_paths:
                    raise ValueError(f"Invalid model type: {model_type}")
                try:
                    path_index = int(path_index)
                except (TypeError, ValueError):
                    raise ValueError("Invalid pathIndex")
                if path_index < 0 or path_index >= len(folder_paths.folder_names_and_paths[model_type][0]):
                    raise ValueError(f"Invalid pathIndex: {path_index}")
                if not fullname:
                    raise ValueError("Fullname is required")
                if url and not isinstance(url, str):
                    raise ValueError("Invalid URL")

                model_path = utils.get_full_path(model_type, path_index, fullname)
                if os.path.exists(model_path):
                    raise ValueError(f"Model already exists at {model_path}")

                task_id = f"download_{model_type}_{path_index}_{id(request)}"
                async with self.lock:
                    if task_id in self.running_tasks:
                        return web.json_response({"success": True, "task_id": task_id, "status": "running"})
                    self.running_tasks[task_id] = {
                        "status": "running",
                        "results": {"fullname": fullname, "downloadedSize": 0, "totalSize": 0, "bps": 0},
                        "error": None
                    }

                # Create download task properly without blocking
                asyncio.create_task(self._run_download_task(task_id, url, model_path, fullname))
                logger.info(f"Download task started: {task_id}")
                return web.json_response({"success": True, "task_id": task_id, "status": "started"})

            except Exception as e:
                error_msg = f"Start download failed: {str(e)}"
                utils.print_error(error_msg)
                return web.json_response({"success": False, "error": error_msg})

    async def _run_scan_task(self, folder: str, request, task_id: str):
        """Non-blocking scan task runner"""
        try:
            results = await self.scan_models(folder, request, task_id)
            async with self.lock:
                self.running_tasks[task_id]["results"] = results
                self.running_tasks[task_id]["status"] = "completed"
            
            # Send completion event in non-blocking way
            asyncio.create_task(self._send_websocket_message("complete_scan_task", {
                "task_id": task_id, 
                "results": results
            }))
        except Exception as e:
            async with self.lock:
                self.running_tasks[task_id]["status"] = "failed"
                self.running_tasks[task_id]["error"] = str(e)
            
            # Send error event in non-blocking way
            asyncio.create_task(self._send_websocket_message("error_scan_task", {
                "task_id": task_id, 
                "error": str(e)
            }))

    async def _run_download_task(self, task_id: str, url: str, model_path: str, fullname: str):
        """Non-blocking download task runner"""
        try:
            logger.info(f"Starting download task: {task_id}, URL: {url}, Path: {model_path}")
            
            # Simulate download progress (replace with actual download logic)
            for i in range(1, 4):
                await asyncio.sleep(1)  # Non-blocking sleep
                
                progress_data = {
                    "fullname": fullname,
                    "downloadedSize": i * 100,
                    "totalSize": 300,
                    "bps": 100
                }
                
                async with self.lock:
                    self.running_tasks[task_id]["results"].update(progress_data)
                
                # Send progress update in non-blocking way
                asyncio.create_task(self._send_websocket_message("update_download_task", {
                    "task_id": task_id,
                    **progress_data
                }))
            
            async with self.lock:
                self.running_tasks[task_id]["status"] = "completed"
                self.running_tasks[task_id]["results"] = {"path": model_path, "fullname": fullname}
            
            # Send completion event in non-blocking way
            asyncio.create_task(self._send_websocket_message("complete_download_task", {
                "task_id": task_id, 
                "path": model_path
            }))
            
        except Exception as e:
            async with self.lock:
                self.running_tasks[task_id]["status"] = "failed"
                self.running_tasks[task_id]["error"] = str(e)
            
            # Send error event in non-blocking way
            asyncio.create_task(self._send_websocket_message("error_download_task", {
                "task_id": task_id, 
                "error": str(e)
            }))

    async def _send_websocket_message(self, event_type: str, data: dict):
        """Non-blocking WebSocket message sender"""
        try:
            # Use asyncio.create_task to prevent blocking
            await utils.send_json(event_type, data)
        except Exception as e:
            logger.error(f"Failed to send WebSocket message {event_type}: {str(e)}")

    async def scan_models(self, folder: str, request, task_id: str = None):
        """Non-blocking model scanner"""
        result = []
        include_hidden_files = utils.get_setting_value(request, "scan.include_hidden_files", False)
        folders, *others = folder_paths.folder_names_and_paths[folder]

        def get_file_info(entry: str, base_path: str, path_index: int):
            """Synchronous file info getter (runs in executor)"""
            prefix_path = utils.normalize_path(base_path)
            if not prefix_path.endswith("/"):
                prefix_path = f"{prefix_path}/"

            full_path = os.path.join(base_path, entry)
            is_file = os.path.isfile(full_path)
            relative_path = utils.normalize_path(full_path).replace(prefix_path, "")
            sub_folder = os.path.dirname(relative_path)
            filename = os.path.basename(relative_path)
            basename = os.path.splitext(filename)[0] if is_file else filename
            extension = os.path.splitext(filename)[1] if is_file else ""

            if is_file and extension not in folder_paths.supported_pt_extensions:
                return None

            preview_type = "image"
            preview_ext = ".webp"
            preview_images = utils.get_model_all_images(full_path)
            if len(preview_images) > 0:
                preview_type = "image"
                preview_ext = ".webp"
            else:
                preview_videos = utils.get_model_all_videos(full_path)
                if len(preview_videos) > 0:
                    preview_type = "video"
                    preview_ext = f".{preview_videos[0].split('.')[-1]}"

            model_preview = f"/model-manager/preview/{folder}/{path_index}/{relative_path.replace(extension, preview_ext)}"

            stat = os.stat(full_path)
            return {
                "type": folder,
                "subFolder": sub_folder,
                "isFolder": not is_file,
                "basename": basename,
                "extension": extension,
                "pathIndex": path_index,
                "sizeBytes": stat.st_size if is_file else 0,
                "preview": model_preview if is_file else None,
                "previewType": preview_type,
                "createdAt": round(stat.st_ctime_ns / 1000000),
                "updatedAt": round(stat.st_mtime_ns / 1000000),
            }

        for path_index, base_path in enumerate(folders):
            if not os.path.exists(base_path):
                continue
                
            # Get file entries in executor to prevent blocking
            loop = asyncio.get_event_loop()
            file_entries = await loop.run_in_executor(
                self.executor, 
                functools.partial(utils.recursive_search_files_sync, base_path, request)
            )
            
            # Process files in executor to prevent blocking
            file_info_tasks = []
            for entry in file_entries:
                task = loop.run_in_executor(self.executor, get_file_info, entry, base_path, path_index)
                file_info_tasks.append(task)
            
            # Process results as they complete
            for completed_task in asyncio.as_completed(file_info_tasks):
                file_info = await completed_task
                if file_info is None:
                    continue
                    
                result.append(file_info)
                
                # Send progress update if scanning with task_id
                if task_id:
                    async with self.lock:
                        self.running_tasks[task_id]["results"].append(file_info)
                    
                    # Send update in non-blocking way
                    asyncio.create_task(self._send_websocket_message("update_scan_task", {
                        "task_id": task_id, 
                        "file": file_info
                    }))

        return result

    def get_model_info(self, model_path: str):
        """Synchronous model info getter (called from executor)"""
        directory = os.path.dirname(model_path)
        metadata = utils.get_model_metadata(model_path)
        description_file = utils.get_model_description_name(model_path)
        description_file = utils.join_path(directory, description_file)
        description = None
        if os.path.isfile(description_file):
            with open(description_file, "r", encoding="utf-8", newline="") as f:
                description = f.read()
        return {
            "metadata": metadata,
            "description": description,
        }

    def update_model(self, model_path: str, model_data: dict):
        """Synchronous model updater (called from executor)"""
        if "previewFile" in model_data:
            previewFile = model_data["previewFile"]
            if isinstance(previewFile, str) and previewFile == "undefined":
                utils.remove_model_preview_image(model_path)
            else:
                utils.save_model_preview_image(model_path, previewFile)
        if "description" in model_data:
            description = model_data["description"]
            utils.save_model_description(model_path, description)
        if "type" in model_data and "pathIndex" in model_data and "fullname" in model_data:
            model_type = model_data.get("type", None)
            path_index = int(model_data.get("pathIndex", None))
            fullname = model_data.get("fullname", None)
            if model_type is None or path_index is None or fullname is None:
                raise RuntimeError("Invalid type or pathIndex or fullname")
            model_type = model_type + 's' if model_type == 'checkpoint' else model_type
            new_model_path = utils.get_full_path(model_type, path_index, fullname)
            utils.rename_model(model_path, new_model_path)

    def remove_model(self, model_path: str):
        """Synchronous model remover (called from executor)"""
        model_dirname = os.path.dirname(model_path)
        os.remove(model_path)
        model_previews = utils.get_model_all_images(model_path)
        for preview in model_previews:
            os.remove(utils.join_path(model_dirname, preview))
        model_descriptions = utils.get_model_all_descriptions(model_path)
        for description in model_descriptions:
            os.remove(utils.join_path(model_dirname, description))

    async def shutdown(self):
        """Graceful shutdown"""
        self._shutdown = True
        self.executor.shutdown(wait=True)

model_manager = ModelManager()

def get_instance():
    return model_manager

# Integration with ComfyUI
import server
routes = server.PromptServer.instance.routes
model_manager.add_routes(routes)
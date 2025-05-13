import os
import folder_paths
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from aiohttp import web
from . import utils

class ModelManager:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.lock = threading.Lock()
        self.running_tasks = {}  # task_id -> {status, results, error}

    def add_routes(self, routes):
        @routes.get("/model-manager/base-folders")
        @utils.deprecated(reason="Use `/model-manager/models` instead.")
        async def get_model_paths(request):
            """
            Returns the base folders for models.
            """
            model_base_paths = utils.resolve_model_base_paths()
            return web.json_response({"success": True, "data": model_base_paths})

        @routes.get("/model-manager/models")
        async def get_folders(request):
            """
            Returns the base folders for models.
            """
            try:
                result = utils.resolve_model_base_paths()
                return web.json_response({"success": True, "data": result})
            except Exception as e:
                error_msg = f"Read models failed: {str(e)}"
                utils.print_error(error_msg)
                return web.json_response({"success": False, "error": error_msg})

        @routes.get("/model-manager/scan/start")
        async def start_scan(request):
            """
            Starts a model scan in the background and returns a task ID.
            """
            folder = request.query.get("folder", None)
            if not folder:
                return web.json_response({"success": False, "error": "Folder parameter is required"})
            
            task_id = f"scan_{folder}_{id(request)}"
            with self.lock:
                if task_id in self.running_tasks:
                    return web.json_response({"success": True, "task_id": task_id, "status": "running"})

                self.running_tasks[task_id] = {"status": "running", "results": [], "error": None}

            async def scan_task():
                try:
                    results = await self.scan_models(folder, request, task_id)
                    with self.lock:
                        self.running_tasks[task_id]["results"] = results
                        self.running_tasks[task_id]["status"] = "completed"
                        await utils.send_json("complete_scan_task", {"task_id": task_id, "results": results})
                except Exception as e:
                    with self.lock:
                        self.running_tasks[task_id]["status"] = "failed"
                        self.running_tasks[task_id]["error"] = str(e)
                        await utils.send_json("error_scan_task", {"task_id": task_id, "error": str(e)})

            self.executor.submit(lambda: self.loop.run_until_complete(scan_task()))
            return web.json_response({"success": True, "task_id": task_id, "status": "started"})

        @routes.get("/model-manager/scan/status/{task_id}")
        async def get_scan_status(request):
            """
            Returns the status and partial results of a scan task.
            """
            task_id = request.match_info.get("task_id", None)
            with self.lock:
                task = self.running_tasks.get(task_id, {"status": "not_found", "results": [], "error": None})
            return web.json_response({"success": True, "status": task["status"], "data": task["results"], "error": task["error"]})

        @routes.get("/model-manager/models/{folder}")
        async def get_folder_models(request):
            """
            Returns models in a folder (synchronous, kept for compatibility).
            """
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
            """
            Get the information of the specified model.
            """
            model_type = request.match_info.get("type", None)
            path_index = int(request.match_info.get("index", None))
            filename = request.match_info.get("filename", None)

            try:
                model_path = utils.get_valid_full_path(model_type, path_index, filename)
                result = self.get_model_info(model_path)
                return web.json_response({"success": True, "data": result})
            except Exception as e:
                error_msg = f"Read model info failed: {str(e)}"
                utils.print_error(error_msg)
                return web.json_response({"success": False, "error": error_msg})

        @routes.put("/model-manager/model/{type}/{index}/{filename:.*}")
        async def update_model(request):
            """
            Update model information.

            request body: x-www-form-urlencoded
            - previewFile: preview file.
            - description: description.
            - type: model type.
            - pathIndex: index of the model folders.
            - fullname: filename that relative to the model folder.
            All fields are optional, but type, pathIndex and fullname must appear together.
            """
            model_type = request.match_info.get("type", None)
            path_index = int(request.match_info.get("index", None))
            filename = request.match_info.get("filename", None)

            model_data = await request.post()
            model_data = dict(model_data)

            try:
                model_path = utils.get_valid_full_path(model_type, path_index, filename)
                if model_path is None:
                    raise RuntimeError(f"File {filename} not found")
                self.update_model(model_path, model_data)
                return web.json_response({"success": True})
            except Exception as e:
                error_msg = f"Update model failed: {str(e)}"
                utils.print_error(error_msg)
                return web.json_response({"success": False, "error": error_msg})

        @routes.delete("/model-manager/model/{type}/{index}/{filename:.*}")
        async def delete_model(request):
            """
            Delete model.
            """
            model_type = request.match_info.get("type", None)
            path_index = int(request.match_info.get("index", None))
            filename = request.match_info.get("filename", None)

            try:
                model_path = utils.get_valid_full_path(model_type, path_index, filename)
                if model_path is None:
                    raise RuntimeError(f"File {filename} not found")
                self.remove_model(model_path)
                return web.json_response({"success": True})
            except Exception as e:
                error_msg = f"Delete model failed: {str(e)}"
                utils.print_error(error_msg)
                return web.json_response({"success": False, "error": error_msg})

    async def scan_models(self, folder: str, request, task_id: str = None):
        result = []
        include_hidden_files = utils.get_setting_value(request, "scan.include_hidden_files", False)
        folders, *others = folder_paths.folder_names_and_paths[folder]

        def get_file_info(entry: str, base_path: str, path_index: int):
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
            async def progress_callback(file_path: str):
                if task_id:
                    file_info = get_file_info(file_path, base_path, path_index)
                    if file_info:
                        with self.lock:
                            self.running_tasks[task_id]["results"].append(file_info)
                            await utils.send_json("update_scan_task", {"task_id": task_id, "file": file_info})

            file_entries = await utils.recursive_search_files(base_path, request, progress_callback if task_id else None)
            with ThreadPoolExecutor() as executor:
                futures = {executor.submit(get_file_info, entry, base_path, path_index): entry for entry in file_entries}
                for future in as_completed(futures):
                    file_info = future.result()
                    if file_info is None:
                        continue
                    result.append(file_info)

        return result

    def get_model_info(self, model_path: str):
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
            new_model_path = utils.get_full_path(model_type, path_index, fullname)
            utils.rename_model(model_path, new_model_path)

    def remove_model(self, model_path: str):
        model_dirname = os.path.dirname(model_path)
        os.remove(model_path)
        model_previews = utils.get_model_all_images(model_path)
        for preview in model_previews:
            os.remove(utils.join_path(model_dirname, preview))
        model_descriptions = utils.get_model_all_descriptions(model_path)
        for description in model_descriptions:
            os.remove(utils.join_path(model_dirname, description))

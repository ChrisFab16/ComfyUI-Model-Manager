import os
import re
import uuid
import math
import yaml
import requests
import markdownify
import json
from PIL import Image
from io import BytesIO
from aiohttp import web
from abc import ABC, abstractmethod
from urllib.parse import urlparse, parse_qs

import folder_paths

from . import utils, config, thread


class ModelSearcher(ABC):
    """
    Abstract class for model searcher.
    """

    @abstractmethod
    def search_by_url(self, url: str) -> list[dict]:
        pass

    @abstractmethod
    def search_by_hash(self, hash: str) -> dict:
        pass


class UnknownWebsiteSearcher(ModelSearcher):
    def search_by_url(self, url: str):
        raise RuntimeError(f"Unknown Website, please input a URL from huggingface.co or civitai.com.")

    def search_by_hash(self, hash: str):
        raise RuntimeError(f"Unknown Website, unable to search with hash value.")


class CivitaiModelSearcher(ModelSearcher):
    def search_by_url(self, url: str):
        parsed_url = urlparse(url)

        pathname = parsed_url.path
        match = re.match(r"^/models/(\d*)", pathname)
        model_id = match.group(1) if match else None

        query_params = parse_qs(parsed_url.query)
        version_id = query_params.get("modelVersionId", [None])[0]

        if not model_id:
            return []

        # Set up headers with API key if available
        headers = {
            'User-Agent': 'ComfyUI-Model-Manager/1.0',
            'Accept': 'application/json'
        }
        api_key = utils.get_setting_value(None, "api_key.civitai")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        response = None
        max_retries = 3
        retry_delay = 1  # seconds

        for attempt in range(max_retries):
            try:
                response = requests.get(
                    f"https://civitai.com/api/v1/models/{model_id}",
                    headers=headers,
                    timeout=30
                )
                
                # Break if successful
                if response.status_code == 200:
                    break
                    
                # Handle specific error cases
                if response.status_code == 401:
                    raise RuntimeError("Unauthorized: Please check your Civitai API key")
                elif response.status_code == 404:
                    raise RuntimeError("Model not found on Civitai")
                elif response.status_code == 429:
                    if attempt < max_retries - 1:  # If not the last attempt
                        import time
                        time.sleep(retry_delay * (attempt + 1))
                        continue
                    raise RuntimeError("Rate limit exceeded. Please try again later")
                elif response.status_code >= 500:
                    if attempt < max_retries - 1:  # If not the last attempt
                        import time
                        time.sleep(retry_delay * (attempt + 1))
                        continue
                    raise RuntimeError(f"Civitai server error (HTTP {response.status_code}). Please try again later")
                
                # Handle other error cases
                try:
                    error_data = response.json()
                    error_msg = error_data.get('message', f'HTTP {response.status_code}')
                except:
                    error_msg = f'HTTP {response.status_code}'
                raise RuntimeError(f"Failed to fetch model info: {error_msg}")
                
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:  # If not the last attempt
                    continue
                raise RuntimeError("Request to Civitai timed out. Please try again later")
            except requests.exceptions.ConnectionError:
                if attempt < max_retries - 1:  # If not the last attempt
                    continue
                raise RuntimeError("Failed to connect to Civitai. Please check your internet connection")
            except requests.exceptions.RequestException as e:
                raise RuntimeError(f"Failed to fetch model info: {str(e)}")

        try:
            res_data: dict = response.json()
        except ValueError:
            raise RuntimeError("Invalid JSON response from Civitai")

        model_versions: list[dict] = res_data.get("modelVersions", [])
        if not model_versions:
            raise RuntimeError("No model versions found")

        if version_id:
            model_versions = utils.filter_with(model_versions, {"id": int(version_id)})
            if not model_versions:
                raise RuntimeError(f"Model version {version_id} not found")

        models: list[dict] = []

        for version in model_versions:
            model_files: list[dict] = version.get("files", [])
            model_files = utils.filter_with(model_files, {"type": "Model"})

            if not model_files:
                continue

            shortname = version.get("name", None) if len(model_files) > 0 else None

            for file in model_files:
                name = file.get("name", None)
                if not name:
                    continue

                extension = os.path.splitext(name)[1]
                basename = os.path.splitext(name)[0]

                metadata_info = {
                    "website": "Civitai",
                    "modelPage": f"https://civitai.com/models/{model_id}?modelVersionId={version.get('id')}",
                    "author": res_data.get("creator", {}).get("username", None),
                    "baseModel": version.get("baseModel"),
                    "hashes": file.get("hashes"),
                    "metadata": file.get("metadata"),
                    "preview": [i["url"] for i in version.get("images", [])],
                }

                description_parts: list[str] = []
                description_parts.append("---")
                description_parts.append(yaml.dump(metadata_info).strip())
                description_parts.append("---")
                description_parts.append("")
                description_parts.append(f"# Trigger Words")
                description_parts.append("")
                description_parts.append(", ".join(version.get("trainedWords", ["No trigger words"])))
                description_parts.append("")
                description_parts.append(f"# About this version")
                description_parts.append("")
                description_parts.append(markdownify.markdownify(version.get("description", "<p>No description about this version</p>")).strip())
                description_parts.append("")
                description_parts.append(f"# {res_data.get('name')}")
                description_parts.append("")
                description_parts.append(markdownify.markdownify(res_data.get("description", "<p>No description about this model</p>")).strip())
                description_parts.append("")

                model = {
                    "id": file.get("id"),
                    "shortname": shortname or basename,
                    "basename": basename,
                    "extension": extension,
                    "preview": metadata_info.get("preview"),
                    "sizeBytes": file.get("sizeKB", 0) * 1024,
                    "type": self._resolve_model_type(res_data.get("type", "")),
                    "pathIndex": 0,
                    "subFolder": "",
                    "description": "\n".join(description_parts),
                    "metadata": file.get("metadata"),
                    "downloadPlatform": "civitai",
                    "downloadUrl": file.get("downloadUrl"),
                    "hashes": file.get("hashes"),
                }
                models.append(model)

        if not models:
            raise RuntimeError("No downloadable model files found")

        return models

    def search_by_hash(self, hash: str):
        if not hash:
            raise RuntimeError(f"Hash value is empty.")

        response = requests.get(f"https://civitai.com/api/v1/model-versions/by-hash/{hash}")
        response.raise_for_status()
        version: dict = response.json()

        model_id = version.get("modelId")
        version_id = version.get("id")

        model_page = f"https://civitai.com/models/{model_id}?modelVersionId={version_id}"

        models = self.search_by_url(model_page)

        for model in models:
            sha256 = model.get("hashes", {}).get("SHA256")
            if sha256 == hash:
                return model

        return models[0]

    def _resolve_model_type(self, model_type: str):
        map_legacy = {
            "TextualInversion": "embeddings",
            "LoCon": "loras",
            "DoRA": "loras",
            "Controlnet": "controlnet",
            "Upscaler": "upscale_models",
            "VAE": "vae",
            "unknown": "",
        }
        return map_legacy.get(model_type, f"{model_type.lower()}s")


class HuggingfaceModelSearcher(ModelSearcher):
    def search_by_url(self, url: str):
        parsed_url = urlparse(url)

        pathname = parsed_url.path

        space, name, *rest_paths = pathname.strip("/").split("/")

        model_id = f"{space}/{name}"
        rest_pathname = "/".join(rest_paths)

        response = requests.get(f"https://huggingface.co/api/models/{model_id}")
        response.raise_for_status()
        res_data: dict = response.json()

        sibling_files: list[str] = [x.get("rfilename") for x in res_data.get("siblings", [])]

        model_files = utils.filter_with(
            utils.filter_with(sibling_files, self._match_model_files()),
            self._match_tree_files(rest_pathname),
        )

        image_files = utils.filter_with(
            utils.filter_with(sibling_files, self._match_image_files()),
            self._match_tree_files(rest_pathname),
        )
        image_files = [f"https://huggingface.co/{model_id}/resolve/main/{filename}" for filename in image_files]

        models: list[dict] = []

        for filename in model_files:
            fullname = os.path.basename(filename)
            extension = os.path.splitext(fullname)[1]
            basename = os.path.splitext(fullname)[0]

            description_parts: list[str] = []
            description_parts.append("---")
            description_parts.append(yaml.dump({
                "website": "Hugging Face",
                "modelPage": f"https://huggingface.co/{model_id}",
                "author": res_data.get("author", None),
                "preview": image_files,
            }).strip())
            description_parts.append("---")
            description_parts.append("")
            description_parts.append(f"# {res_data.get('modelId')}")
            description_parts.append("")
            description_parts.append(res_data.get("description", "No description about this model"))
            description_parts.append("")

            model = {
                "id": None,
                "shortname": basename,
                "basename": basename,
                "extension": extension,
                "preview": image_files,
                "sizeBytes": 0,
                "type": "",
                "pathIndex": 0,
                "subFolder": os.path.dirname(filename),
                "description": "\n".join(description_parts),
                "metadata": None,
                "downloadPlatform": "huggingface",
                "downloadUrl": f"https://huggingface.co/{model_id}/resolve/main/{filename}",
                "hashes": None,
            }
            models.append(model)

        return models

    def search_by_hash(self, hash: str):
        raise RuntimeError(f"Hugging Face does not support searching by hash value.")

    def _match_model_files(self):
        def _filter_model_files(file: str):
            extension = os.path.splitext(file)[1]
            return extension in folder_paths.supported_pt_extensions
        return _filter_model_files

    def _match_image_files(self):
        def _filter_image_files(file: str):
            extension = os.path.splitext(file)[1].lower()
            return extension in [".jpg", ".jpeg", ".png", ".webp"]
        return _filter_image_files

    def _match_tree_files(self, pathname: str):
        def _filter_tree_files(file: str):
            if not pathname:
                return True
            return file.startswith(pathname)
        return _filter_tree_files


class Information:
    def add_routes(self, routes):
        @routes.get("/model-manager/model-info")
        async def fetch_model_info(request):
            """
            Fetch model information from network with model page.
            """
            try:
                model_page = request.query.get("model-page", None)
                result = self.fetch_model_info(model_page)
                return web.json_response({"success": True, "data": result})
            except Exception as e:
                error_msg = f"Fetch model info failed: {str(e)}"
                utils.print_error(error_msg)
                return web.json_response({"success": False, "error": error_msg})

        @routes.get("/model-manager/model-info/scan")
        async def get_model_info_download_task(request):
            """
            Get model information download task list.
            """
            try:
                result = self.get_scan_model_info_task_list()
                if result is not None:
                    await self.download_model_info(request)
                return web.json_response({"success": True, "data": result})
            except Exception as e:
                error_msg = f"Get model info download task list failed: {str(e)}"
                utils.print_error(error_msg)
                return web.json_response({"success": False, "error": error_msg})

        @routes.post("/model-manager/model-info/scan")
        async def create_model_info_download_task(request):
            """
            Create a task to download model information.

            - scanMode: The alternatives are diff and full.
            - mode: The alternatives are diff and full.
            - path: Scanning root path.
            """
            post = await utils.get_request_body(request)
            try:
                # TODO scanMode is deprecated, use mode instead.
                scan_mode = post.get("scanMode", "diff")
                scan_mode = post.get("mode", scan_mode)
                scan_path = post.get("path", None)
                result = await self.create_scan_model_info_task(scan_mode, scan_path, request)
                return web.json_response({"success": True, "data": result})
            except Exception as e:
                error_msg = f"Download model info failed: {str(e)}"
                utils.print_error(error_msg)
                return web.json_response({"success": False, "error": error_msg})

        @routes.get("/model-manager/preview/{type}/{index}/{filename:.*}")
        async def read_model_preview(request):
            """
            Get the file stream of the specified image.
            If the file does not exist, no-preview.png is returned.

            :param type: The type of the model. eg.checkpoints, loras, vae, etc.
            :param index: The index of the model folders.
            :param filename: The filename of the image.
            """
            model_type = request.match_info.get("type", None)
            index = int(request.match_info.get("index", None))
            filename = request.match_info.get("filename", None)

            content_type = utils.resolve_file_content_type(filename)

            if content_type == "video":
                abs_path = utils.get_full_path(model_type, index, filename)
                return web.FileResponse(abs_path)

            extension_uri = config.extension_uri

            try:
                folders = folder_paths.get_folder_paths(model_type)
                base_path = folders[index]
                abs_path = utils.join_path(base_path, filename)
                preview_name = utils.get_model_preview_name(abs_path)
                if preview_name:
                    dir_name = os.path.dirname(abs_path)
                    abs_path = utils.join_path(dir_name, preview_name)
            except:
                abs_path = extension_uri

            if not os.path.isfile(abs_path):
                abs_path = utils.join_path(extension_uri, "assets", "no-preview.png")

            image_data = self.get_image_preview_data(abs_path)
            return web.Response(body=image_data.getvalue(), content_type="image/webp")

        @routes.get("/model-manager/preview/download/{filename}")
        async def read_download_preview(request):
            filename = request.match_info.get("filename", None)
            extension_uri = config.extension_uri

            download_path = utils.get_download_path()
            preview_path = utils.join_path(download_path, filename)

            if not os.path.isfile(preview_path):
                preview_path = utils.join_path(extension_uri, "assets", "no-preview.png")

            return web.FileResponse(preview_path)

    def get_image_preview_data(self, filename: str):
        with Image.open(filename) as img:
            max_size = 1024
            original_format = img.format

            exif_data = img.info.get("exif")
            icc_profile = img.info.get("icc_profile")

            if getattr(img, "is_animated", False) and img.n_frames > 1:
                total_frames = img.n_frames
                step = max(1, math.ceil(total_frames / 30))

                frames, durations = [], []

                for frame_idx in range(0, total_frames, step):
                    img.seek(frame_idx)
                    frame = img.copy()
                    frame.thumbnail((max_size, max_size), Image.Resampling.NEAREST)

                    frames.append(frame)
                    durations.append(img.info.get("duration", 100) * step)

                save_args = {
                    "format": "WEBP",
                    "save_all": True,
                    "append_images": frames[1:],
                    "duration": durations,
                    "loop": 0,
                    "quality": 80,
                    "method": 0,
                    "allow_mixed": False,
                }

                if exif_data:
                    save_args["exif"] = exif_data

                if icc_profile:
                    save_args["icc_profile"] = icc_profile

                img_byte_arr = BytesIO()
                frames[0].save(img_byte_arr, **save_args)
                img_byte_arr.seek(0)
                return img_byte_arr

            img.thumbnail((max_size, max_size), Image.Resampling.BICUBIC)

            img_byte_arr = BytesIO()
            save_args = {"format": "WEBP", "quality": 80}

            if exif_data:
                save_args["exif"] = exif_data
            if icc_profile:
                save_args["icc_profile"] = icc_profile

            img.save(img_byte_arr, **save_args)
            img_byte_arr.seek(0)
            return img_byte_arr

    def fetch_model_info(self, model_page: str):
        if not model_page:
            return []

        model_searcher = self.get_model_searcher_by_url(model_page)
        result = model_searcher.search_by_url(model_page)
        return result

    def get_scan_information_task_filepath(self):
        download_dir = utils.get_download_path()
        return utils.join_path(download_dir, "scan_information.task")

    def get_scan_model_info_task_list(self):
        scan_info_task_file = self.get_scan_information_task_filepath()
        if os.path.isfile(scan_info_task_file):
            return utils.load_dict_pickle_file(scan_info_task_file)
        return None

    async def create_scan_model_info_task(self, scan_mode: str, scan_path: str | None, request):
        """Create a task to scan and update model information.
        
        Args:
            scan_mode: Either 'diff' (scan changed files) or 'full' (scan all files)
            scan_path: Optional specific path to scan, or None for all model paths
            request: The web request object
            
        Returns:
            Dict containing task information
        """
        scan_info_task_file = self.get_scan_information_task_filepath()
        scan_info_task_content = {
            "mode": scan_mode,
            "status": "running",
            "progress": 0,
            "total_models": 0,
            "processed_models": 0,
            "errors": []
        }

        # Get paths to scan
        scan_paths: list[str] = []
        if scan_path is None:
            model_base_paths = utils.resolve_model_base_paths()
            for model_type in model_base_paths:
                folders = folder_paths.get_folder_paths(model_type)
                scan_paths.extend([utils.normalize_path(p) for p in folders if os.path.exists(p)])
        else:
            scan_paths = [utils.normalize_path(scan_path)]

        # Find all model files
        scan_models: dict[str, bool] = {}
        for base_path in scan_paths:
            try:
                files = utils.recursive_search_files(base_path, request)
                models = folder_paths.filter_files_extensions(files, folder_paths.supported_pt_extensions)
                for fullname in models:
                    fullname = utils.normalize_path(fullname)
                    abs_model_path = utils.join_path(base_path, fullname)
                    scan_models[abs_model_path] = False
                    utils.print_debug(f"Found model: {abs_model_path}")
            except Exception as e:
                error = f"Error scanning path {base_path}: {str(e)}"
                scan_info_task_content["errors"].append(error)
                utils.print_error(error)

        scan_info_task_content["models"] = scan_models
        scan_info_task_content["total_models"] = len(scan_models)
        
        # Save initial task state
        utils.save_dict_pickle_file(scan_info_task_file, scan_info_task_content)
        await utils.send_json("update_scan_information_task", scan_info_task_content)
        
        # Start scanning
        await self.download_model_info(request)
        return scan_info_task_content

    async def download_model_info(self, request):
        """Download and update model information for all models in the scan task."""
        
        async def download_information_task(task_id: str):
            scan_info_task_file = self.get_scan_information_task_filepath()
            scan_info_task_content = utils.load_dict_pickle_file(scan_info_task_file)
            
            scan_mode = scan_info_task_content.get("mode", "diff")
            scan_models = scan_info_task_content.get("models", {})
            total_models = len(scan_models)
            processed = 0

            for model_path in scan_models:
                if scan_models[model_path]:
                    continue

                try:
                    # Check if we need to update this model
                    needs_update = True
                    if scan_mode == "diff":
                        metadata = utils.get_model_metadata(model_path)
                        if metadata:
                            needs_update = False
                            scan_models[model_path] = True
                            processed += 1
                            continue

                    if needs_update:
                        # Calculate hash and search for info
                        hash_value = utils.calculate_sha256(model_path)
                        if hash_value:
                            try:
                                model_searcher = CivitaiModelSearcher()
                                model_info = model_searcher.search_by_hash(hash_value)
                                
                                if model_info:
                                    # Save description as metadata
                                    utils.save_model_description(model_path, {
                                        "description": model_info.get("description"),
                                        "source": "civitai",
                                        "hash": hash_value,
                                        **model_info.get("metadata", {})
                                    })
                                    
                                    # Save preview image if available
                                    preview_urls = model_info.get("preview", [])
                                    if preview_urls:
                                        utils.save_model_preview_image(model_path, preview_urls[0], "civitai")
                            except Exception as e:
                                error = f"Error fetching info for {model_path}: {str(e)}"
                                scan_info_task_content["errors"].append(error)
                                utils.print_error(error)

                    scan_models[model_path] = True
                    processed += 1
                    
                    # Update progress
                    scan_info_task_content["processed_models"] = processed
                    scan_info_task_content["progress"] = (processed / total_models) * 100
                    utils.save_dict_pickle_file(scan_info_task_file, scan_info_task_content)
                    await utils.send_json("update_scan_information_task", scan_info_task_content)
                    
                except Exception as e:
                    error = f"Error processing {model_path}: {str(e)}"
                    scan_info_task_content["errors"].append(error)
                    utils.print_error(error)

            # Mark task as complete
            scan_info_task_content["status"] = "completed"
            scan_info_task_content["progress"] = 100
            utils.save_dict_pickle_file(scan_info_task_file, scan_info_task_content)
            await utils.send_json("update_scan_information_task", scan_info_task_content)
            
            # Clean up task file
            try:
                os.remove(scan_info_task_file)
            except Exception as e:
                utils.print_error(f"Error removing task file: {str(e)}")
            
            utils.print_info("Completed model information scan")

        task_id = str(uuid.uuid4())
        self.download_thread_pool.submit(download_information_task, task_id)

    def get_model_searcher_by_url(self, url: str) -> ModelSearcher:
        parsed_url = urlparse(url)
        hostname = parsed_url.hostname

        if hostname == "civitai.com":
            return CivitaiModelSearcher()
        elif hostname == "huggingface.co":
            return HuggingfaceModelSearcher()
        else:
            return UnknownWebsiteSearcher() 
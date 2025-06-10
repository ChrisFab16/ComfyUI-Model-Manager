import os
import hashlib
import datetime
import glob
from aiohttp import web, WSMsgType
import aiohttp
import traceback

import folder_paths
from . import utils
from .scan_worker import ModelScanWorker
from .websocket_manager import WebSocketManager


class ModelManager:
    def add_routes(self, routes):
        @routes.get("/model-manager/base-folders")
        @utils.deprecated(reason="Use `/model-manager/models` instead.")
        async def get_model_paths(request):
            """
            Returns the base folders for models.
            """
            model_base_paths = utils.resolve_model_base_paths()
            return web.json_response({"success": True, "data": model_base_paths})

        @routes.get("/model-manager/preview/{folder}/{index}/{filename:.*}")
        async def get_preview(request):
            """Serve model preview images."""
            try:
                folder = request.match_info.get("folder", None)
                path_index = int(request.match_info.get("index", None))
                filename = request.match_info.get("filename", None)
                
                utils.print_info(f"Preview request - folder: {folder}, index: {path_index}, filename: {filename}")
                
                # Handle default preview
                if folder == "default" and filename == "no-preview.png":
                    default_preview = os.path.join(os.path.dirname(__file__), "assets", "no-preview.png")
                    utils.print_info(f"Default preview path: {default_preview}")
                    if os.path.exists(default_preview):
                        return web.FileResponse(default_preview, headers={"Content-Type": "image/png"})
                    return web.Response(status=404)
                
                if not folder or not filename:
                    raise ValueError("Missing folder or filename")
                    
                # Get the model path
                model_filename = filename.replace(".preview.png", ".safetensors")
                utils.print_info(f"Looking for model: {model_filename}")
                model_path = utils.get_valid_full_path(folder, path_index, model_filename)
                utils.print_info(f"Found model path: {model_path}")
                
                if not model_path:
                    raise ValueError(f"Model not found: {filename}")
                    
                # Get preview file path
                preview_name = utils.get_model_preview_name(model_path)
                utils.print_info(f"Preview name: {preview_name}")
                if not preview_name:
                    raise ValueError(f"No preview for model: {filename}")
                    
                preview_path = utils.join_path(os.path.dirname(model_path), preview_name)
                utils.print_info(f"Preview path: {preview_path}")
                if not os.path.exists(preview_path):
                    raise ValueError(f"Preview file not found: {preview_name}")
                    
                # Determine content type
                content_type = utils.resolve_file_content_type(preview_path)
                if not content_type:
                    content_type = "image/png"  # Default to PNG
                utils.print_info(f"Content type: {content_type}")
                    
                # Return the file
                return web.FileResponse(preview_path, headers={"Content-Type": content_type})
                
            except Exception as e:
                error_msg = f"Failed to get preview: {str(e)}"
                utils.print_error(error_msg)
                return web.json_response({"success": False, "error": error_msg}, status=404)

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

        @routes.get("/model-manager/models/{folder}")
        async def get_folder_models(request):
            try:
                folder = request.match_info.get("folder", None)
                if not folder:
                    raise ValueError("Folder parameter is required")
                    
                if folder not in folder_paths.folder_names_and_paths:
                    raise ValueError(f"Invalid folder type: {folder}")
                    
                # Get scan worker instance
                scan_worker = ModelScanWorker.get_instance()
                
                # Check for cached results
                cached_results = scan_worker.get_cached_results(folder)
                if cached_results is not None:
                    utils.print_info(f"Returning cached results for {folder}")
                    # Transform models for frontend
                    transformed_results = utils.transform_model_for_frontend(cached_results)
                    return web.json_response({
                        "success": True,
                        "data": transformed_results,
                        "is_scanning": scan_worker.is_scanning(folder)
                    })
                
                # Start background scan
                include_hidden_files = utils.get_setting_value(request, "scan.include_hidden_files", False)
                scan_worker.start_scan(folder, include_hidden_files)
                
                # Return empty list with scanning status
                return web.json_response({
                    "success": True,
                    "data": [],
                    "is_scanning": True
                })
            except Exception as e:
                error_msg = f"Read models failed: {str(e)}"
                utils.print_error(error_msg)
                return web.json_response({"success": False, "error": error_msg})

        @routes.get("/model-manager/model/{type}/{index}/{filename:.*}")
        async def get_model_info(request):
            """
            Get the information of the specified model.
            """
            try:
                model_type = request.match_info.get("type", None)
                if not model_type:
                    raise ValueError("Model type is required")
                    
                path_index = int(request.match_info.get("index", None))
                filename = request.match_info.get("filename", None)
                if not filename:
                    raise ValueError("Filename is required")

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

        @routes.get("/model-manager/websocket/status")
        async def get_websocket_status(request):
            """Get WebSocket connection status."""
            try:
                ws_manager = WebSocketManager.get_instance()
                return web.json_response({
                    "success": True,
                    "data": ws_manager.get_status()
                })
            except Exception as e:
                error_msg = f"Failed to get WebSocket status: {str(e)}"
                utils.print_error(error_msg)
                return web.json_response({"success": False, "error": error_msg})

        @routes.post("/model-manager/websocket/reconnect")
        async def reconnect_websocket(request):
            """Force WebSocket reconnection."""
            try:
                ws_manager = WebSocketManager.get_instance()
                # Close all existing connections to force reconnection
                for ws in list(ws_manager._websocket_clients):
                    try:
                        await ws.close()
                    except:
                        pass
                ws_manager._websocket_clients.clear()
                return web.json_response({"success": True})
            except Exception as e:
                error_msg = f"Failed to reconnect WebSocket: {str(e)}"
                utils.print_error(error_msg)
                return web.json_response({"success": False, "error": error_msg})

        @routes.get("/model-manager/websocket/messages")
        async def get_websocket_messages(request):
            """Get pending WebSocket messages."""
            try:
                ws_manager = WebSocketManager.get_instance()
                status = ws_manager.get_status()
                return web.json_response({
                    "success": True,
                    "data": {
                        "connected": status["total_clients"] > 0,
                        "server_clients": status["server_clients"],
                        "plugin_clients": status["plugin_clients"]
                    }
                })
            except Exception as e:
                error_msg = f"Failed to get WebSocket messages: {str(e)}"
                utils.print_error(error_msg)
                return web.json_response({"success": False, "error": error_msg})

        @routes.get("/model-manager/ws")
        async def websocket_handler(request):
            """WebSocket endpoint for real-time updates."""
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            
            # Register client
            ws_manager = WebSocketManager.get_instance()
            ws_manager.add_client(ws)
            
            try:
                async for msg in ws:
                    if msg.type == WSMsgType.TEXT:
                        # Handle incoming messages if needed
                        pass
                    elif msg.type == WSMsgType.ERROR:
                        utils.print_error(f"WebSocket connection closed with exception {ws.exception()}")
            finally:
                # Unregister client
                ws_manager.remove_client(ws)
                
            return ws

    def should_replace_duplicate(self, existing: dict, new_path: str) -> bool:
        """Decide which copy of a duplicate file to keep."""
        existing_path = existing['path']
        
        # Prefer files in standard locations
        existing_standard = self.is_standard_location(existing_path)
        new_standard = self.is_standard_location(new_path)
        if existing_standard and not new_standard:
            return False
        if new_standard and not existing_standard:
            return True
        
        # Prefer files with more metadata
        existing_meta = len(existing['info'].get('metadata', {}))
        new_meta = len(utils.get_model_metadata(new_path))
        if existing_meta > new_meta:
            return False
        if new_meta > existing_meta:
            return True
        
        # Prefer files with previews
        existing_preview = bool(utils.get_model_preview_name(existing_path))
        new_preview = bool(utils.get_model_preview_name(new_path))
        if existing_preview and not new_preview:
            return False
        if new_preview and not existing_preview:
            return True
        
        # Default to keeping existing
        return False
    
    def is_standard_location(self, path: str) -> bool:
        """Check if a path is in a standard model location."""
        normalized = utils.normalize_path(path).lower()
        return any(type_dir in normalized.split('/') 
                  for type_dir in ['checkpoints', 'loras', 'vae', 'clip'])
    
    def get_preview_info(self, model_path: str, folder: str, path_index: int) -> dict:
        """Get preview image/video information for a model."""
        preview_name = utils.get_model_preview_name(model_path)
        if preview_name and os.path.exists(os.path.join(os.path.dirname(model_path), preview_name)):
            return {
                'type': 'image',
                'url': f"/model-manager/preview/{folder}/{path_index}/{preview_name}"
            }
        
        # Return default preview
        return {
            'type': 'image',
            'url': "/model-manager/assets/no-preview.png"
        }

    def get_all_files_entry(self, directory: str, include_hidden_files: bool = False) -> list[os.DirEntry[str]]:
        """Get all files in a directory recursively."""
        entries: list[os.DirEntry[str]] = []
        try:
            with os.scandir(directory) as it:
                for entry in it:
                    # Skip hidden files
                    if not include_hidden_files and entry.name.startswith("."):
                        continue
                    entries.append(entry)
                    if entry.is_dir():
                        entries.extend(self.get_all_files_entry(entry.path, include_hidden_files))
        except Exception as e:
            utils.print_error(f"Error scanning directory {directory}: {str(e)}")
        return entries

    def scan_models(self, folder: str, request):
        """Scan models in a folder and return model information.
        
        Args:
            folder: The folder type to scan (e.g. 'loras', 'checkpoints')
            request: The web request object
            
        Returns:
            List of model information dictionaries
        """
        result = []
        seen_files = {}  # Track unique files by content hash
        
        include_hidden_files = utils.get_setting_value(request, "scan.include_hidden_files", False)
        
        try:
            folders, extensions = folder_paths.folder_names_and_paths[folder]
            # Deduplicate and normalize paths
            folders = list(set(utils.normalize_path(f) for f in folders))
            # Sort paths for consistent indexing
            folders.sort()
        except KeyError:
            raise ValueError(f"Invalid folder type: {folder}")
        except ValueError as e:
            raise ValueError(f"Error getting folder paths: {str(e)}")

        utils.print_info(f"Starting scan for model type: {folder}")
        utils.print_info(f"Configured paths: {', '.join(folders)}")
        utils.print_info(f"Supported extensions: {', '.join(extensions)}")

        def get_file_info(entry: os.DirEntry[str], base_path: str, path_index: int):
            try:
                if not entry.is_file():
                    return None
                    
                # Get basic file info
                full_path = entry.path
                prefix_path = utils.normalize_path(base_path)
                if not prefix_path.endswith("/"):
                    prefix_path = f"{prefix_path}/"
                    
                relative_path = utils.normalize_path(full_path).replace(prefix_path, "")
                extension = os.path.splitext(relative_path)[1]
                
                # Skip unsupported files
                if extension not in folder_paths.supported_pt_extensions:
                    utils.print_debug(f"Skipping unsupported file type: {full_path}")
                    return None
                    
                # Calculate file hash for deduplication
                file_hash = utils.calculate_sha256(full_path)
                if not file_hash:  # Skip if hash calculation failed
                    return None
                    
                if file_hash in seen_files:
                    # If we've seen this file before, check which copy to keep
                    existing = seen_files[file_hash]
                    if self.should_replace_duplicate(existing['info'], full_path):
                        # Remove existing entry
                        result.remove(existing['info'])
                    else:
                        utils.print_debug(f"Skipping duplicate file: {full_path}")
                        return None
                
                # Get rich metadata
                metadata = utils.get_model_metadata(full_path)
                
                # Ensure preview exists
                preview_name = utils.get_model_preview_name(full_path)
                if not preview_name or not os.path.exists(os.path.join(os.path.dirname(full_path), preview_name)):
                    # Try to generate preview from metadata
                    if metadata.get("preview_url"):
                        try:
                            utils.save_model_preview_image(full_path, metadata["preview_url"])
                            utils.print_info(f"Generated preview for {full_path} from preview_url")
                        except Exception as e:
                            utils.print_error(f"Failed to generate preview for {full_path}: {e}")
                
                # Get preview info
                preview_info = self.get_preview_info(full_path, folder, path_index)
                
                # Build model info
                model_info = {
                    "path_index": path_index,
                    "sub_folder": os.path.dirname(relative_path),
                    "filename": os.path.basename(relative_path),
                    "basename": os.path.splitext(os.path.basename(relative_path))[0],
                    "extension": extension,
                    "preview": preview_info['url'],
                    "preview_type": preview_info['type'],
                    "size": entry.stat().st_size,
                    "mtime": entry.stat().st_mtime,
                    "metadata": metadata,
                    
                    # Additional fields
                    "hash": file_hash,
                    "model_type": metadata.get("model_type") or utils.get_model_type_from_path(full_path),
                    "display_name": metadata.get("name_for_display", os.path.splitext(os.path.basename(full_path))[0]),
                    "description": metadata.get("description", ""),
                    "tags": metadata.get("tags", []),
                    "trigger_words": metadata.get("trigger_words", []),
                    "base_model": metadata.get("base_model"),
                    "source": metadata.get("source"),
                    "license": metadata.get("license")
                }
                
                # Track this file
                seen_files[file_hash] = {
                    'path': full_path,
                    'info': model_info
                }
                
                return model_info
                
            except Exception as e:
                utils.print_error(f"Error processing file {entry.path}: {str(e)}")
                return None

        # Scan all configured paths
        for path_index, base_path in enumerate(folders):
            if not os.path.exists(base_path):
                utils.print_warning(f"Path does not exist: {base_path}")
                continue
            
            utils.print_info(f"Scanning path {path_index + 1}/{len(folders)}: {base_path}")
            
            try:
                file_entries = self.get_all_files_entry(base_path, include_hidden_files)
                with ThreadPoolExecutor() as executor:
                    futures = {executor.submit(get_file_info, entry, base_path, path_index): entry 
                              for entry in file_entries}
                    for future in as_completed(futures):
                        try:
                            file_info = future.result()
                            if file_info is not None:
                                result.append(file_info)
                        except Exception as e:
                            utils.print_error(f"Error processing file entry: {str(e)}")
            except Exception as e:
                utils.print_error(f"Error scanning path {base_path}: {str(e)}")

        # Sort results
        result.sort(key=lambda x: (x['sub_folder'], x['filename']))
        
        utils.print_info(f"Scan completed for {folder}. Found {len(result)} unique models.")
        return result

    def get_model_info(self, model_path: str):
        directory = os.path.dirname(model_path)

        metadata = utils.get_model_metadata(model_path)

        description_file = utils.get_model_description_name(model_path)
        description_file = utils.join_path(directory, description_file) if description_file else None
        description = None
        if description_file and os.path.exists(description_file):
            with open(description_file, "r", encoding="utf-8") as f:
                description = f.read()

        preview_name = utils.get_model_preview_name(model_path)
        preview_file = utils.join_path(directory, preview_name) if preview_name else None

        return {
            "metadata": metadata,
            "description": description,
            "preview": preview_file,
        }

    def update_model(self, model_path: str, model_data: dict):
        """
        Update model information.
        """
        # Update preview
        preview_file = model_data.get("previewFile", None)
        if preview_file:
            utils.save_model_preview_image(model_path, preview_file)

        # Update description
        description = model_data.get("description", None)
        if description:
            utils.save_model_description(model_path, description)

        # Move model
        new_type = model_data.get("type", None)
        new_path_index = model_data.get("pathIndex", None)
        new_fullname = model_data.get("fullname", None)
        if new_type and new_path_index and new_fullname:
            new_model_path = utils.get_full_path(new_type, int(new_path_index), new_fullname)
            utils.rename_model(model_path, new_model_path)

    def remove_model(self, model_path: str):
        """
        Remove model and its associated files.
        """
        if not os.path.exists(model_path):
            return

        directory = os.path.dirname(model_path)
        basename = os.path.splitext(os.path.basename(model_path))[0]

        # Remove preview images
        for ext in [".preview.*", ".jpg", ".jpeg", ".png", ".webp"]:
            for preview_file in glob.glob(os.path.join(directory, basename + ext)):
                try:
                    os.remove(preview_file)
                except:
                    pass

        # Remove preview videos
        for ext in [".mp4", ".webm"]:
            preview_file = os.path.join(directory, basename + ext)
            if os.path.exists(preview_file):
                try:
                    os.remove(preview_file)
                except:
                    pass

        # Remove description files
        for ext in [".txt", ".md"]:
            description_file = os.path.join(directory, basename + ext)
            if os.path.exists(description_file):
                try:
                    os.remove(description_file)
                except:
                    pass

        # Remove metadata file
        metadata_file = os.path.join(directory, basename + ".json")
        if os.path.exists(metadata_file):
            try:
                os.remove(metadata_file)
            except:
                pass

        # Remove model file
        try:
            os.remove(model_path)
        except:
            pass 
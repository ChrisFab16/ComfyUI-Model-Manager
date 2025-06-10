import os
import time
import json
import asyncio
import threading
import folder_paths
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Set

from . import utils
from . import config
from .websocket_manager import WebSocketManager

class ModelScanWorker:
    _instance = None
    _lock = threading.Lock()
    
    def __init__(self):
        self._scan_cache: Dict[str, List[dict]] = {}  # folder -> model list
        self._scan_times: Dict[str, float] = {}  # folder -> last scan time
        self._scanning: Set[str] = set()  # Currently scanning folders
        self._scan_thread: Optional[threading.Thread] = None
        self._cache_lifetime = 300  # Cache lifetime in seconds (5 minutes)
        self._loop = asyncio.get_event_loop()
        self._cache_file = os.path.join(config.CACHE_ROOT, "model_scan_cache.json")
        self._load_cache()
        
    def _load_cache(self):
        """Load cached scan results from disk."""
        try:
            if os.path.exists(self._cache_file):
                with open(self._cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    self._scan_cache = cache_data.get('scan_cache', {})
                    self._scan_times = cache_data.get('scan_times', {})
                    utils.print_info(f"Loaded scan cache for {len(self._scan_cache)} folders")
        except Exception as e:
            utils.print_error(f"Failed to load scan cache: {str(e)}")
            self._scan_cache = {}
            self._scan_times = {}
            
    def _save_cache(self):
        """Save current scan results to disk."""
        try:
            os.makedirs(config.CACHE_ROOT, exist_ok=True)
            cache_data = {
                'scan_cache': self._scan_cache,
                'scan_times': self._scan_times
            }
            with open(self._cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2)
            utils.print_info(f"Saved scan cache for {len(self._scan_cache)} folders")
        except Exception as e:
            utils.print_error(f"Failed to save scan cache: {str(e)}")
        
    @classmethod
    def get_instance(cls) -> 'ModelScanWorker':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
        
    async def _broadcast_message(self, message: dict):
        """Helper method to broadcast a message via WebSocket."""
        try:
            ws_manager = WebSocketManager.get_instance()
            await ws_manager.broadcast(message["type"], message["data"])
        except Exception as e:
            utils.print_error(f"Failed to broadcast message: {str(e)}")
        
    def get_cached_results(self, folder: str) -> Optional[List[dict]]:
        """Get cached scan results if they exist and are not too old."""
        if folder not in self._scan_cache:
            return None
            
        last_scan = self._scan_times.get(folder, 0)
        if time.time() - last_scan > self._cache_lifetime:
            return None
            
        return self._scan_cache[folder]
        
    def is_scanning(self, folder: str) -> bool:
        """Check if a folder is currently being scanned."""
        return folder in self._scanning
        
    def start_scan(self, folder: str, include_hidden_files: bool = False):
        """Start a background scan of the specified folder."""
        if folder in self._scanning:
            utils.print_info(f"Scan already in progress for {folder}")
            return
            
        def scan_thread():
            self._scanning.add(folder)
            try:
                results = self._scan_folder(folder, include_hidden_files)
                self._scan_cache[folder] = results
                self._scan_times[folder] = time.time()
                self._save_cache()  # Save cache after successful scan
                
                # Notify clients of scan completion
                asyncio.run_coroutine_threadsafe(
                    self._broadcast_message({
                        "type": "scan_complete",
                        "data": {
                            "folder": folder,
                            "count": len(results)
                        }
                    }), 
                    self._loop
                )
            except Exception as e:
                utils.print_error(f"Error scanning folder {folder}: {str(e)}")
                # Notify clients of scan error
                asyncio.run_coroutine_threadsafe(
                    self._broadcast_message({
                        "type": "scan_error",
                        "data": {
                            "folder": folder,
                            "error": str(e)
                        }
                    }),
                    self._loop
                )
            finally:
                self._scanning.remove(folder)
        
        self._scan_thread = threading.Thread(target=scan_thread)
        self._scan_thread.daemon = True
        self._scan_thread.start()
        
    def _scan_folder(self, folder: str, include_hidden_files: bool) -> List[dict]:
        """Perform the actual folder scan."""
        result = []
        seen_files = {}  # Track unique files by content hash
        
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
                
                # Notify clients of new model found
                asyncio.run_coroutine_threadsafe(
                    self._broadcast_message({
                        "type": "model_found",
                        "data": {
                            "folder": folder,
                            "model": utils.transform_model_for_frontend(model_info)
                        }
                    }),
                    self._loop
                )
                
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
        
    def get_all_files_entry(self, directory: str, include_hidden_files: bool = False) -> List[os.DirEntry[str]]:
        """Get all files in a directory recursively."""
        entries: List[os.DirEntry[str]] = []
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
        preview_images = utils.get_model_all_images(model_path)
        if preview_images:
            preview_name = os.path.basename(preview_images[0])
            return {
                'type': 'image',
                'url': f"/model-manager/preview/{folder}/{path_index}/{preview_name}"
            }
        return {
            'type': 'image',
            'url': "/model-manager/assets/no-preview.png"
        } 
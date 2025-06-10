"""Metadata refresh system for ComfyUI Model Manager."""

import os
import json
import hashlib
import asyncio
from typing import Dict, Any, List, Optional, Callable
from aiohttp import web

from . import utils
from . import config
from .information import CivitaiModelSearcher
from .api_key import ApiKey

class MetadataRefresh:
    """Handles metadata refreshing for models with incomplete or missing data."""
    
    def __init__(self):
        """Initialize the metadata refresh system."""
        self.api_key = ApiKey()
        self.searcher = CivitaiModelSearcher()
        
    def add_routes(self, routes):
        """Add metadata refresh API routes."""
        
        @routes.get("/model-manager/model/{type}/{index}/{filename:.*}/metadata/refresh")
        async def refresh_model_metadata(request):
            """Refresh metadata for a specific model."""
            try:
                model_type = request.match_info.get("type", None)
                path_index = int(request.match_info.get("index", None))
                filename = request.match_info.get("filename", None)
                
                if not all([model_type, filename]):
                    raise ValueError("Model type and filename are required")
                
                model_path = utils.get_valid_full_path(model_type, path_index, filename)
                if not model_path or not os.path.exists(model_path):
                    raise ValueError(f"Model file not found: {filename}")
                
                result = await self.refresh_single_model(model_path)
                return web.json_response({"success": True, "data": result})
                
            except Exception as e:
                error_msg = f"Failed to refresh metadata: {str(e)}"
                utils.print_error(error_msg)
                return web.json_response({"success": False, "error": error_msg})
        
        @routes.post("/model-manager/batch/metadata/refresh")
        async def batch_refresh_metadata(request):
            """Refresh metadata for multiple models."""
            try:
                request_data = await request.json()
                model_paths = request_data.get("models", [])
                force_refresh = request_data.get("force", False)
                
                if not model_paths:
                    raise ValueError("No models specified for refresh")
                
                results = await self.refresh_batch_models(model_paths, force_refresh)
                return web.json_response({"success": True, "data": results})
                
            except Exception as e:
                error_msg = f"Failed to batch refresh metadata: {str(e)}"
                utils.print_error(error_msg)
                return web.json_response({"success": False, "error": error_msg})
        
        @routes.get("/model-manager/maintenance/scan")
        async def scan_incomplete_metadata(request):
            """Scan for models with incomplete or missing metadata."""
            try:
                model_type = request.query.get("type", None)
                include_previews = request.query.get("include_previews", "true").lower() == "true"
                
                results = await self.scan_for_incomplete_metadata(model_type, include_previews)
                return web.json_response({"success": True, "data": results})
                
            except Exception as e:
                error_msg = f"Failed to scan for incomplete metadata: {str(e)}"
                utils.print_error(error_msg)
                return web.json_response({"success": False, "error": error_msg})
        
        @routes.post("/model-manager/preview/regenerate")
        async def regenerate_previews(request):
            """Regenerate missing preview images."""
            try:
                request_data = await request.json()
                model_paths = request_data.get("models", [])
                
                if not model_paths:
                    raise ValueError("No models specified for preview regeneration")
                
                results = await self.regenerate_preview_images(model_paths)
                return web.json_response({"success": True, "data": results})
                
            except Exception as e:
                error_msg = f"Failed to regenerate previews: {str(e)}"
                utils.print_error(error_msg)
                return web.json_response({"success": False, "error": error_msg})

    async def refresh_single_model(self, model_path: str) -> Dict[str, Any]:
        """Refresh metadata for a single model."""
        try:
            print(f"[ComfyUI Model Manager] Refreshing metadata for {model_path}")
            
            # Get current metadata
            current_metadata = utils.get_model_metadata(model_path)
            
            # Check completeness
            completeness = self._assess_metadata_completeness(current_metadata)
            
            if completeness == "complete":
                print(f"[ComfyUI Model Manager] Metadata already complete for {os.path.basename(model_path)}")
                return {
                    "status": "already_complete",
                    "path": model_path,
                    "completeness": completeness
                }
            
            # Calculate hash for searching
            file_hash = utils.calculate_sha256(model_path)
            if not file_hash:
                raise RuntimeError("Failed to calculate file hash")
            
            # Search for model information
            print(f"[ComfyUI Model Manager] Searching for model info using hash: {file_hash[:8]}...")
            model_info = self.searcher.search_by_hash(file_hash)
            
            if not model_info:
                print(f"[ComfyUI Model Manager] No model info found for {os.path.basename(model_path)}")
                return {
                    "status": "not_found",
                    "path": model_path,
                    "hash": file_hash,
                    "completeness": completeness
                }
            
            # Update metadata
            await self._update_model_metadata(model_path, model_info, current_metadata)
            
            # Download preview if missing
            if not utils.get_model_preview_name(model_path):
                preview_urls = model_info.get("preview", [])
                if preview_urls:
                    try:
                        utils.save_model_preview_image(model_path, preview_urls[0], "civitai")
                        print(f"[ComfyUI Model Manager] Downloaded preview image for {os.path.basename(model_path)}")
                    except Exception as e:
                        print(f"[ComfyUI Model Manager] Failed to download preview: {e}")
            
            # Get updated completeness
            updated_metadata = utils.get_model_metadata(model_path)
            updated_completeness = self._assess_metadata_completeness(updated_metadata)
            
            print(f"[ComfyUI Model Manager] Metadata refresh complete for {os.path.basename(model_path)}")
            
            return {
                "status": "updated",
                "path": model_path,
                "hash": file_hash,
                "old_completeness": completeness,
                "new_completeness": updated_completeness,
                "found_info": bool(model_info)
            }
            
        except Exception as e:
            print(f"[ComfyUI Model Manager] Error refreshing metadata for {model_path}: {e}")
            return {
                "status": "error",
                "path": model_path,
                "error": str(e)
            }

    async def refresh_batch_models(self, model_paths: List[str], force_refresh: bool = False) -> Dict[str, Any]:
        """Refresh metadata for multiple models."""
        results = {
            "processed": 0,
            "updated": 0,
            "errors": 0,
            "already_complete": 0,
            "not_found": 0,
            "details": []
        }
        
        for model_path in model_paths:
            if not os.path.exists(model_path):
                results["errors"] += 1
                results["details"].append({
                    "path": model_path,
                    "status": "error",
                    "error": "File not found"
                })
                continue
            
            # Skip if already complete (unless forced)
            if not force_refresh:
                current_metadata = utils.get_model_metadata(model_path)
                if self._assess_metadata_completeness(current_metadata) == "complete":
                    results["already_complete"] += 1
                    results["details"].append({
                        "path": model_path,
                        "status": "already_complete"
                    })
                    results["processed"] += 1
                    continue
            
            result = await self.refresh_single_model(model_path)
            results["processed"] += 1
            results["details"].append(result)
            
            if result["status"] == "updated":
                results["updated"] += 1
            elif result["status"] == "error":
                results["errors"] += 1
            elif result["status"] == "not_found":
                results["not_found"] += 1
            elif result["status"] == "already_complete":
                results["already_complete"] += 1
        
        return results

    async def scan_for_incomplete_metadata(self, model_type: Optional[str] = None, include_previews: bool = True) -> Dict[str, Any]:
        """Scan for models with incomplete or missing metadata."""
        incomplete_models = []
        
        # Get model types to scan
        model_types = [model_type] if model_type else utils.resolve_model_base_paths().keys()
        
        for mtype in model_types:
            try:
                import folder_paths
                folder_paths_list = folder_paths.get_folder_paths(mtype)
                
                for path_index, folder_path in enumerate(folder_paths_list):
                    if not os.path.exists(folder_path):
                        continue
                    
                    for file_entry in os.scandir(folder_path):
                        if file_entry.is_file() and file_entry.name.endswith(('.safetensors', '.ckpt', '.pt', '.pth')):
                            model_path = file_entry.path
                            
                            # Get metadata
                            metadata = utils.get_model_metadata(model_path)
                            completeness = self._assess_metadata_completeness(metadata)
                            
                            # Check preview if requested
                            has_preview = bool(utils.get_model_preview_name(model_path)) if include_previews else True
                            
                            if completeness != "complete" or (include_previews and not has_preview):
                                incomplete_models.append({
                                    "path": model_path,
                                    "filename": file_entry.name,
                                    "type": mtype,
                                    "pathIndex": path_index,
                                    "completeness": completeness,
                                    "has_preview": has_preview,
                                    "size": file_entry.stat().st_size,
                                    "issues": self._identify_metadata_issues(metadata, has_preview)
                                })
                                
            except Exception as e:
                print(f"[ComfyUI Model Manager] Error scanning {mtype}: {e}")
        
        return {
            "total_incomplete": len(incomplete_models),
            "models": incomplete_models,
            "scanned_types": list(model_types)
        }

    async def regenerate_preview_images(self, model_paths: List[str]) -> Dict[str, Any]:
        """Regenerate missing preview images."""
        results = {
            "processed": 0,
            "generated": 0,
            "errors": 0,
            "already_exists": 0,
            "no_source": 0,
            "details": []
        }
        
        for model_path in model_paths:
            try:
                if not os.path.exists(model_path):
                    results["errors"] += 1
                    results["details"].append({
                        "path": model_path,
                        "status": "error",
                        "error": "File not found"
                    })
                    continue
                
                # Check if preview already exists
                if utils.get_model_preview_name(model_path):
                    results["already_exists"] += 1
                    results["details"].append({
                        "path": model_path,
                        "status": "already_exists"
                    })
                    results["processed"] += 1
                    continue
                
                # Get metadata for preview URL
                metadata = utils.get_model_metadata(model_path)
                preview_url = metadata.get("preview_url")
                
                if not preview_url:
                    # Try to find from raw metadata
                    raw_metadata = metadata.get("raw_metadata", {})
                    preview_urls = raw_metadata.get("preview", [])
                    if preview_urls and isinstance(preview_urls, list):
                        preview_url = preview_urls[0]
                
                if not preview_url:
                    results["no_source"] += 1
                    results["details"].append({
                        "path": model_path,
                        "status": "no_source"
                    })
                    results["processed"] += 1
                    continue
                
                # Download preview
                utils.save_model_preview_image(model_path, preview_url, "civitai")
                results["generated"] += 1
                results["details"].append({
                    "path": model_path,
                    "status": "generated",
                    "preview_url": preview_url
                })
                results["processed"] += 1
                
            except Exception as e:
                results["errors"] += 1
                results["details"].append({
                    "path": model_path,
                    "status": "error",
                    "error": str(e)
                })
                results["processed"] += 1
        
        return results

    def _assess_metadata_completeness(self, metadata: Dict[str, Any]) -> str:
        """Assess the completeness of model metadata."""
        if not metadata:
            return "minimal"
        
        # Required fields for complete metadata
        required_fields = ["description", "trigger_words", "base_model"]
        optional_fields = ["source", "source_url", "license", "tags"]
        
        has_required = all(metadata.get(field) for field in required_fields)
        has_optional = sum(1 for field in optional_fields if metadata.get(field))
        
        if has_required and has_optional >= 2:
            return "complete"
        elif has_required or has_optional >= 1:
            return "partial"
        else:
            return "minimal"

    def _identify_metadata_issues(self, metadata: Dict[str, Any], has_preview: bool) -> List[str]:
        """Identify specific issues with metadata."""
        issues = []
        
        if not metadata.get("description"):
            issues.append("missing_description")
        
        if not metadata.get("trigger_words"):
            issues.append("missing_trigger_words")
        
        if not metadata.get("base_model"):
            issues.append("missing_base_model")
        
        if not metadata.get("source"):
            issues.append("missing_source")
        
        if not has_preview:
            issues.append("missing_preview")
        
        return issues

    async def _update_model_metadata(self, model_path: str, model_info: Dict[str, Any], current_metadata: Dict[str, Any]) -> None:
        """Update model metadata with new information."""
        # Merge new information with existing metadata
        updated_metadata = current_metadata.copy()
        
        # Update from model_info
        if model_info.get("description"):
            updated_metadata["description"] = model_info["description"]
        
        if model_info.get("trainedWords"):
            updated_metadata["trigger_words"] = model_info["trainedWords"]
        
        if model_info.get("baseModel"):
            updated_metadata["base_model"] = model_info["baseModel"]
        
        if model_info.get("source"):
            updated_metadata["source"] = model_info["source"]
        
        if model_info.get("modelPage"):
            updated_metadata["source_url"] = model_info["modelPage"]
        
        if model_info.get("tags"):
            updated_metadata["tags"] = model_info["tags"]
        
        # Store raw metadata for reference
        updated_metadata["raw_metadata"] = model_info
        
        # Save updated metadata
        utils.save_model_description(model_path, updated_metadata) 
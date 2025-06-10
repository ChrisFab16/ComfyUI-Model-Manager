"""Download validation system for ComfyUI Model Manager."""

import os
import hashlib
import requests
from typing import Dict, Any, Optional, List
from aiohttp import web

from . import utils
from . import config
from .api_key import ApiKey

class DownloadValidator:
    """Validates downloads and ensures file integrity."""
    
    def __init__(self):
        """Initialize the download validator."""
        self.api_key = ApiKey()
    
    def add_routes(self, routes):
        """Add download validation API routes."""
        
        @routes.post("/model-manager/download/validate")
        async def validate_download(request):
            """Validate a downloaded model file."""
            try:
                request_data = await request.json()
                model_path = request_data.get("model_path")
                expected_hash = request_data.get("expected_hash")
                expected_size = request_data.get("expected_size")
                
                if not model_path:
                    raise ValueError("Model path is required")
                
                result = await self.validate_model_file(model_path, expected_hash, expected_size)
                return web.json_response({"success": True, "data": result})
                
            except Exception as e:
                error_msg = f"Failed to validate download: {str(e)}"
                utils.print_error(error_msg)
                return web.json_response({"success": False, "error": error_msg})
        
        @routes.get("/model-manager/download/check-auth")
        async def check_download_auth(request):
            """Check if download authentication is working."""
            try:
                platform = request.query.get("platform", "civitai")
                test_url = request.query.get("url")
                
                if not test_url:
                    # Use default test URLs
                    test_urls = {
                        "civitai": "https://civitai.com/api/v1/models",
                        "huggingface": "https://huggingface.co/api/models"
                    }
                    test_url = test_urls.get(platform)
                
                if not test_url:
                    raise ValueError(f"Unsupported platform: {platform}")
                
                result = await self.check_authentication(platform, test_url)
                return web.json_response({"success": True, "data": result})
                
            except Exception as e:
                error_msg = f"Failed to check authentication: {str(e)}"
                utils.print_error(error_msg)
                return web.json_response({"success": False, "error": error_msg})
        
        @routes.post("/model-manager/download/resume")
        async def resume_download(request):
            """Resume a partially downloaded file."""
            try:
                request_data = await request.json()
                download_url = request_data.get("download_url")
                target_path = request_data.get("target_path")
                expected_size = request_data.get("expected_size")
                platform = request_data.get("platform", "civitai")
                
                if not all([download_url, target_path]):
                    raise ValueError("Download URL and target path are required")
                
                result = await self.resume_partial_download(download_url, target_path, expected_size, platform)
                return web.json_response({"success": True, "data": result})
                
            except Exception as e:
                error_msg = f"Failed to resume download: {str(e)}"
                utils.print_error(error_msg)
                return web.json_response({"success": False, "error": error_msg})

    async def validate_model_file(self, model_path: str, expected_hash: Optional[str] = None, expected_size: Optional[int] = None) -> Dict[str, Any]:
        """Validate a model file for completeness and integrity."""
        try:
            print(f"[ComfyUI Model Manager] Validating model file: {model_path}")
            
            if not os.path.exists(model_path):
                return {
                    "valid": False,
                    "error": "File does not exist",
                    "path": model_path
                }
            
            # Get file info
            file_size = os.path.getsize(model_path)
            file_hash = None
            
            # Validate size if provided
            size_valid = True
            if expected_size is not None:
                size_valid = abs(file_size - expected_size) < 1024  # Allow 1KB difference
                if not size_valid:
                    print(f"[ComfyUI Model Manager] Size mismatch: expected {expected_size}, got {file_size}")
            
            # Validate hash if provided
            hash_valid = True
            if expected_hash:
                print(f"[ComfyUI Model Manager] Calculating file hash for validation...")
                file_hash = utils.calculate_sha256(model_path)
                hash_valid = file_hash.lower() == expected_hash.lower()
                if not hash_valid:
                    print(f"[ComfyUI Model Manager] Hash mismatch: expected {expected_hash}, got {file_hash}")
            
            # Check file format
            format_valid = self._validate_model_format(model_path)
            
            # Overall validation
            is_valid = size_valid and hash_valid and format_valid
            
            result = {
                "valid": is_valid,
                "path": model_path,
                "size": file_size,
                "size_valid": size_valid,
                "hash_valid": hash_valid,
                "format_valid": format_valid,
                "file_hash": file_hash,
                "expected_hash": expected_hash,
                "expected_size": expected_size
            }
            
            if not is_valid:
                issues = []
                if not size_valid:
                    issues.append("size_mismatch")
                if not hash_valid:
                    issues.append("hash_mismatch")
                if not format_valid:
                    issues.append("invalid_format")
                result["issues"] = issues
            
            print(f"[ComfyUI Model Manager] Validation result: {'✅ Valid' if is_valid else '❌ Invalid'}")
            return result
            
        except Exception as e:
            print(f"[ComfyUI Model Manager] Error validating file: {e}")
            return {
                "valid": False,
                "error": str(e),
                "path": model_path
            }

    async def check_authentication(self, platform: str, test_url: str) -> Dict[str, Any]:
        """Check if authentication is working for a platform."""
        try:
            print(f"[ComfyUI Model Manager] Checking authentication for {platform}")
            
            # Get API key
            api_key = self.api_key.get_value(platform)
            
            if not api_key:
                return {
                    "authenticated": False,
                    "platform": platform,
                    "error": "No API key configured",
                    "recommendation": f"Please set up your {platform} API key"
                }
            
            # Set up headers
            headers = {"User-Agent": config.user_agent}
            if platform == "civitai":
                headers["Authorization"] = f"Bearer {api_key}"
            elif platform == "huggingface":
                headers["Authorization"] = f"Bearer {api_key}"
            
            # Test request
            response = requests.get(test_url, headers=headers, timeout=10)
            
            authenticated = response.status_code != 401
            
            result = {
                "authenticated": authenticated,
                "platform": platform,
                "status_code": response.status_code,
                "has_api_key": bool(api_key)
            }
            
            if not authenticated:
                if response.status_code == 401:
                    result["error"] = "Invalid API key"
                    result["recommendation"] = f"Please check your {platform} API key"
                elif response.status_code == 403:
                    result["error"] = "API key has insufficient permissions"
                    result["recommendation"] = f"Please check your {platform} API key permissions"
                else:
                    result["error"] = f"HTTP {response.status_code}: {response.reason}"
                    result["recommendation"] = "Please check your internet connection and API key"
            
            print(f"[ComfyUI Model Manager] Authentication check: {'✅ Valid' if authenticated else '❌ Invalid'}")
            return result
            
        except Exception as e:
            print(f"[ComfyUI Model Manager] Error checking authentication: {e}")
            return {
                "authenticated": False,
                "platform": platform,
                "error": str(e),
                "recommendation": "Please check your internet connection and API key"
            }

    async def resume_partial_download(self, download_url: str, target_path: str, expected_size: Optional[int] = None, platform: str = "civitai") -> Dict[str, Any]:
        """Resume a partially downloaded file."""
        try:
            print(f"[ComfyUI Model Manager] Attempting to resume download: {target_path}")
            
            if not os.path.exists(target_path):
                return {
                    "resumable": False,
                    "error": "Partial file does not exist",
                    "target_path": target_path
                }
            
            # Get current file size
            current_size = os.path.getsize(target_path)
            
            if expected_size and current_size >= expected_size:
                return {
                    "resumable": False,
                    "error": "File appears to be complete",
                    "current_size": current_size,
                    "expected_size": expected_size
                }
            
            # Test if server supports range requests
            headers = {"User-Agent": config.user_agent}
            
            # Add authentication if available
            api_key = self.api_key.get_value(platform)
            if api_key:
                if platform == "civitai":
                    headers["Authorization"] = f"Bearer {api_key}"
                elif platform == "huggingface":
                    headers["Authorization"] = f"Bearer {api_key}"
            
            # Test range request
            test_headers = headers.copy()
            test_headers["Range"] = f"bytes={current_size}-{current_size}"
            
            response = requests.head(download_url, headers=test_headers, timeout=10)
            supports_range = response.status_code == 206 or "accept-ranges" in response.headers
            
            if not supports_range:
                return {
                    "resumable": False,
                    "error": "Server does not support range requests",
                    "current_size": current_size,
                    "url": download_url
                }
            
            # Get total size from headers
            content_range = response.headers.get("content-range")
            total_size = None
            if content_range:
                try:
                    total_size = int(content_range.split("/")[1])
                except:
                    pass
            
            if not total_size:
                total_size = int(response.headers.get("content-length", 0))
            
            result = {
                "resumable": True,
                "current_size": current_size,
                "total_size": total_size,
                "remaining_bytes": total_size - current_size if total_size else None,
                "progress_percent": (current_size / total_size * 100) if total_size else None,
                "supports_range": supports_range,
                "authenticated": response.status_code != 401
            }
            
            print(f"[ComfyUI Model Manager] Resume check: {'✅ Resumable' if supports_range else '❌ Not resumable'}")
            return result
            
        except Exception as e:
            print(f"[ComfyUI Model Manager] Error checking resume capability: {e}")
            return {
                "resumable": False,
                "error": str(e),
                "target_path": target_path
            }

    def _validate_model_format(self, model_path: str) -> bool:
        """Validate model file format."""
        try:
            # Check file extension
            _, ext = os.path.splitext(model_path)
            if ext.lower() not in ['.safetensors', '.ckpt', '.pt', '.pth', '.bin']:
                return False
            
            # Basic file header validation
            with open(model_path, 'rb') as f:
                header = f.read(1024)
                
                if ext.lower() == '.safetensors':
                    # SafeTensors files should start with JSON header length
                    if len(header) < 8:
                        return False
                    # Check if first 8 bytes can be interpreted as header length
                    try:
                        header_length = int.from_bytes(header[:8], byteorder='little')
                        return 0 < header_length < 10000000  # Reasonable header size
                    except:
                        return False
                
                elif ext.lower() in ['.ckpt', '.pt', '.pth']:
                    # PyTorch files typically start with specific magic bytes
                    return header.startswith(b'PK') or b'pytorch' in header[:100].lower()
                
                elif ext.lower() == '.bin':
                    # Generic binary check - just ensure it's not empty
                    return len(header) > 0
            
            return True
            
        except Exception as e:
            print(f"[ComfyUI Model Manager] Error validating format: {e}")
            return False

    def pre_download_checks(self, download_info: Dict[str, Any]) -> Dict[str, Any]:
        """Perform pre-download validation checks."""
        checks = {
            "passed": True,
            "warnings": [],
            "errors": [],
            "recommendations": []
        }
        
        # Check required fields
        required_fields = ["downloadUrl", "filename", "type"]
        for field in required_fields:
            if not download_info.get(field):
                checks["errors"].append(f"Missing required field: {field}")
                checks["passed"] = False
        
        # Check file path
        if download_info.get("type") and download_info.get("filename"):
            try:
                target_path = utils.get_full_path(
                    download_info["type"], 
                    download_info.get("pathIndex", 0), 
                    download_info["filename"]
                )
                
                if os.path.exists(target_path):
                    file_size = os.path.getsize(target_path)
                    expected_size = download_info.get("sizeKb", 0) * 1024
                    
                    if expected_size and abs(file_size - expected_size) < 1024:
                        checks["warnings"].append("File already exists with correct size")
                        checks["recommendations"].append("Consider skipping download or use force option")
                    else:
                        checks["warnings"].append("File already exists but size differs")
                        checks["recommendations"].append("File will be overwritten")
            except Exception as e:
                checks["errors"].append(f"Cannot determine target path: {e}")
                checks["passed"] = False
        
        # Check API key for platform
        platform = download_info.get("downloadPlatform", "civitai")
        api_key = self.api_key.get_value(platform)
        if not api_key:
            checks["warnings"].append(f"No {platform} API key configured")
            checks["recommendations"].append(f"Some models may require authentication - consider setting up {platform} API key")
        
        # Check URL accessibility
        download_url = download_info.get("downloadUrl")
        if download_url:
            try:
                response = requests.head(download_url, timeout=5)
                if response.status_code == 401:
                    checks["errors"].append("Authentication required for download")
                    checks["recommendations"].append(f"Please set up your {platform} API key")
                    checks["passed"] = False
                elif response.status_code == 404:
                    checks["errors"].append("Download URL not found")
                    checks["passed"] = False
                elif response.status_code not in [200, 206]:
                    checks["warnings"].append(f"Unexpected response code: {response.status_code}")
            except Exception as e:
                checks["warnings"].append(f"Could not verify download URL: {e}")
        
        return checks 
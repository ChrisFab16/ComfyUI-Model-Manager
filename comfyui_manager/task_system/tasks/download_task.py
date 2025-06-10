"""Download task handler for ComfyUI Model Manager."""

import os
import aiohttp
import asyncio
from typing import Dict, Any, Optional
from ..task_worker import ProgressReporter
import folder_paths

class DownloadModelTask:
    """Task handler for downloading models."""

    def __init__(self, download_dir: str):
        """Initialize the download task handler.
        
        Args:
            download_dir: Directory where models should be downloaded to
        """
        self.download_dir = download_dir

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

    async def __call__(self, task: Dict[str, Any], progress: ProgressReporter, session: Optional[aiohttp.ClientSession] = None) -> Dict[str, Any]:
        """Execute the download task.
        
        Args:
            task: Task parameters including url and model_type
            progress: Progress reporter for updating task status
            session: Optional aiohttp session to use for download
        
        Returns:
            Dict containing download results
        """
        temp_path = None
        try:
            # Get download parameters from task
            params = task['params']
            url = params.get("downloadUrl")  # Changed from url to downloadUrl
            if not url:
                raise ValueError("downloadUrl parameter is required")
            
            model_type = params.get("type")  # Changed from model_type to type
            if not model_type:
                raise ValueError("type parameter is required")
                
            filename = params.get("filename", params.get("basename"))  # Try both filename and basename
            if not filename:
                raise ValueError("filename or basename parameter is required")
                
            path_index = int(params.get("pathIndex", 0))  # Changed from path_index to pathIndex
            expected_size_kb = float(params.get("sizeKb", 0))  # Size in KB
            
            # Get target path
            target_dir = self._get_model_path(model_type, path_index)
            target_path = os.path.join(target_dir, filename)
            
            # Check if file exists and verify size
            if os.path.exists(target_path):
                actual_size_kb = os.path.getsize(target_path) / 1024
                if abs(actual_size_kb - expected_size_kb) < 1:  # Allow 1KB difference
                    return {
                        "success": True,
                        "message": f"Model {filename} already exists",
                        "file_path": target_path,
                        "model_type": model_type
                    }
            
            # Create temporary download path
            temp_path = f"{target_path}.download"
            
            # Create model type directory if it doesn't exist
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            
            # Download file
            should_close_session = False
            if session is None:
                session = aiohttp.ClientSession()
                should_close_session = True
            
            try:
                async with session.get(url) as response:
                    if response.status != 200:
                        raise RuntimeError(f"Download failed with status {response.status}")
                    
                total_size = int(response.headers.get('content-length', 0))
                chunk_size = 8192
                downloaded = 0
                
                with open(temp_path, 'wb') as f:
                    async for chunk in response.content.iter_chunked(chunk_size):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size:
                                await progress(downloaded / total_size * 100)
                
                # Move temp file to final location
                os.replace(temp_path, target_path)
                
                return {
                    "success": True,
                    "message": f"Downloaded {filename} successfully",
                    "file_path": target_path,
                    "model_type": model_type
                }
                
            finally:
                if should_close_session:
                    await session.close()
                    
        except Exception as e:
            # Clean up temp file if it exists
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass  # Ignore cleanup errors
            raise RuntimeError(f"Download failed: {str(e)}") 
"""Download manager for handling model downloads."""

import os
import aiohttp
import asyncio
from typing import Optional, Callable, Dict, Any

from . import config
from . import utils

class DownloadManager:
    """Manages model downloads with progress tracking."""
    
    _instance = None
    
    def __init__(self):
        """Initialize download manager."""
        if DownloadManager._instance is not None:
            raise RuntimeError("DownloadManager is a singleton. Use get_instance() instead.")
        
        # Ensure download directories exist
        os.makedirs(config.CACHE_ROOT, exist_ok=True)
        
    @classmethod
    def get_instance(cls) -> 'DownloadManager':
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = DownloadManager()
        return cls._instance
    
    async def download(
        self,
        url: str,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Dict[str, Any]:
        """
        Download a model from the given URL.
        
        Args:
            url: The URL to download from
            progress_callback: Optional callback for progress updates
            
        Returns:
            Dict containing download results
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        raise RuntimeError(f"Download failed with status {response.status}")
                    
                    # Get total size for progress tracking
                    total_size = int(response.headers.get('content-length', 0))
                    downloaded = 0
                    
                    # Create temporary file for download
                    temp_file = os.path.join(config.CACHE_ROOT, f"download_{utils.generate_uuid()}.tmp")
                    
                    try:
                        with open(temp_file, 'wb') as f:
                            async for chunk in response.content.iter_chunked(config.DOWNLOAD_CHUNK_SIZE):
                                if chunk:
                                    f.write(chunk)
                                    downloaded += len(chunk)
                                    if progress_callback:
                                        progress_callback(len(chunk), total_size)
                        
                        # TODO: Move file to final location based on model type
                        # For now, just return success
                        return {
                            "success": True,
                            "file": temp_file,
                            "size": downloaded,
                            "url": url
                        }
                        
                    except Exception as e:
                        # Clean up temp file on error
                        if os.path.exists(temp_file):
                            os.unlink(temp_file)
                        raise
                        
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "url": url
            } 
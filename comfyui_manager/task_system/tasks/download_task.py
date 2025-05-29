"""Download task handler for ComfyUI Model Manager."""

import os
import aiohttp
import asyncio
from typing import Dict, Any, Optional
from ..task_worker import TaskWorker, ProgressReporter

class DownloadModelTask:
    """Task handler for downloading models."""

    def __init__(self, download_dir: str):
        """Initialize the download task handler.
        
        Args:
            download_dir: Directory where models should be downloaded to
        """
        self.download_dir = download_dir

    async def __call__(self, task: Dict[str, Any], progress: ProgressReporter, session: Optional[aiohttp.ClientSession] = None) -> Dict[str, Any]:
        """Execute the download task.
        
        Args:
            task: Task parameters including url and model_type
            progress: Progress reporter for updating task status
            session: Optional aiohttp session to use for download
        
        Returns:
            Dict containing download results
        """
        url = task['params']['url']
        model_type = task['params']['model_type']
        filename = task['params']['fullname']
        save_path = os.path.join(self.download_dir, model_type, filename)
        temp_path = os.path.join(self.download_dir, f"{task['params'].get('taskId', 'temp')}.download")

        # Create model type directory if it doesn't exist
        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        if session is None:
            session = aiohttp.ClientSession()
            should_close = True
        else:
            should_close = False

        try:
            response = await session.get(url)
            if response.status != 200:
                raise Exception(f"Failed to download model: HTTP {response.status}")

            total_size = int(response.headers.get('content-length', 0))
            chunk_size = 8192
            downloaded = 0

            with open(temp_path, 'wb') as f:
                async for chunk in response.content.iter_chunked(chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size:
                            progress_pct = (downloaded / total_size) * 100
                            await progress(progress_pct)

            # Move the file to its final location
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            os.rename(temp_path, save_path)

            return {
                'success': True,
                'file_path': save_path,
                'size': downloaded,
                'model_type': model_type
            }
        except Exception as e:
            # Clean up partial download if it exists
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise e
        finally:
            if should_close and session is not None:
                await session.close() 
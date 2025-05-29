"""Scan task handler for ComfyUI Model Manager."""

import os
from typing import Dict, Any, List
from ..task_worker import ProgressReporter

class ScanModelTask:
    """Task handler for scanning model directories."""

    def __init__(self, model_dirs: List[str]):
        """Initialize the scan task handler.
        
        Args:
            model_dirs: List of directories to scan for models
        """
        self.model_dirs = model_dirs

    async def __call__(self, task: Dict[str, Any], progress: ProgressReporter) -> Dict[str, Any]:
        """Execute the scan task.
        
        Args:
            task: Task parameters
            progress: Progress reporter for updating task status
        
        Returns:
            Dict containing scan results
        """
        model_files = []
        total_dirs = len(self.model_dirs)
        
        for idx, directory in enumerate(self.model_dirs):
            if not os.path.exists(directory):
                continue

            # Walk through directory and find model files
            for root, _, files in os.walk(directory):
                for file in files:
                    if file.endswith(('.ckpt', '.safetensors', '.pt', '.pth', '.bin')):
                        model_files.append({
                            'path': os.path.join(root, file),
                            'name': file,
                            'type': os.path.basename(os.path.dirname(root)),
                            'size': os.path.getsize(os.path.join(root, file))
                        })
            
            # Update progress after each directory
            progress_pct = ((idx + 1) / total_dirs) * 100
            await progress(progress_pct)

        return {
            'success': True,
            'models': model_files,
            'total_count': len(model_files)
        } 
"""Metadata task handler for ComfyUI Model Manager."""

import os
import json
import hashlib
from typing import Dict, Any, Optional
from ..task_worker import ProgressReporter

class MetadataTask:
    """Task handler for extracting model metadata."""

    def __init__(self, metadata_dir: str):
        """Initialize the metadata task handler.
        
        Args:
            metadata_dir: Directory to store metadata files
        """
        self.metadata_dir = metadata_dir
        os.makedirs(metadata_dir, exist_ok=True)

    async def __call__(self, task: Dict[str, Any], progress: ProgressReporter) -> Dict[str, Any]:
        """Execute the metadata extraction task.
        
        Args:
            task: Task parameters including model_path
            progress: Progress reporter for updating task status
        
        Returns:
            Dict containing metadata results
        """
        model_path = task['params']['model_path']
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")

        # Get model type from path structure (e.g. models/checkpoints/model.safetensors)
        model_type = os.path.basename(os.path.dirname(model_path))

        # Initialize metadata
        metadata = {
            'filename': os.path.basename(model_path),
            'path': model_path,
            'size': os.path.getsize(model_path),
            'type': model_type,
            'hash': None,
            'created': os.path.getctime(model_path),
            'modified': os.path.getmtime(model_path)
        }

        # Calculate file hash (can be time-consuming for large files)
        await progress(0)
        
        sha256_hash = hashlib.sha256()
        total_size = os.path.getsize(model_path)
        processed = 0
        
        with open(model_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256_hash.update(chunk)
                processed += len(chunk)
                progress_pct = (processed / total_size) * 100
                await progress(progress_pct)
        
        metadata['hash'] = sha256_hash.hexdigest()

        # Save metadata to file
        metadata_path = os.path.join(
            self.metadata_dir,
            f"{os.path.splitext(metadata['filename'])[0]}.json"
        )
        
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

        return {
            'success': True,
            'metadata': metadata,
            'metadata_path': metadata_path
        } 
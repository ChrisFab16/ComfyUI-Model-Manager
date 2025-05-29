"""Metadata manager for handling model metadata."""

import os
import json
from typing import Optional, Callable, Dict, Any

from . import config
from . import utils

class MetadataManager:
    """Manages model metadata updates and storage."""
    
    _instance = None
    
    def __init__(self):
        """Initialize metadata manager."""
        if MetadataManager._instance is not None:
            raise RuntimeError("MetadataManager is a singleton. Use get_instance() instead.")
        
    @classmethod
    def get_instance(cls) -> 'MetadataManager':
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = MetadataManager()
        return cls._instance
    
    async def update_metadata(
        self,
        model_path: str,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> Dict[str, Any]:
        """
        Update metadata for a model.
        
        Args:
            model_path: Path to the model file
            progress_callback: Optional callback for progress updates
            
        Returns:
            Dict containing update results
        """
        try:
            if not os.path.exists(model_path):
                raise FileNotFoundError(f"Model file not found: {model_path}")
            
            # Get metadata file path
            metadata_file = os.path.splitext(model_path)[0] + ".info"
            
            # Initialize metadata
            metadata = {
                "name": os.path.basename(model_path),
                "path": model_path,
                "size": os.path.getsize(model_path),
                "type": os.path.splitext(model_path)[1][1:],  # Extension without dot
                "created": utils.get_file_creation_time(model_path),
                "modified": utils.get_file_modification_time(model_path)
            }
            
            # Update progress
            if progress_callback:
                progress_callback(50.0)
            
            # Save metadata
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
            
            # Update progress
            if progress_callback:
                progress_callback(100.0)
            
            return {
                "success": True,
                "metadata": metadata,
                "file": metadata_file
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "path": model_path
            } 
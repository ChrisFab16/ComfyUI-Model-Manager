"""Model manager for handling model scanning and organization."""

import os
from typing import Optional, Callable, Dict, Any, List

from . import config
from . import utils

class ModelManager:
    """Manages model scanning and organization."""
    
    _instance = None
    
    def __init__(self):
        """Initialize model manager."""
        if ModelManager._instance is not None:
            raise RuntimeError("ModelManager is a singleton. Use get_instance() instead.")
        
        # Ensure model directories exist
        os.makedirs(config.MODELS_ROOT, exist_ok=True)
        
    @classmethod
    def get_instance(cls) -> 'ModelManager':
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = ModelManager()
        return cls._instance
    
    async def scan_models(
        self,
        folder: str,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Dict[str, Any]:
        """
        Scan a folder for models.
        
        Args:
            folder: The folder to scan
            progress_callback: Optional callback for progress updates
            
        Returns:
            Dict containing scan results
        """
        try:
            models = []
            errors = []
            
            # Get list of files to scan
            all_files = []
            for root, _, files in os.walk(folder):
                for file in files:
                    if any(file.endswith(ext) for ext in config.SUPPORTED_MODEL_EXTENSIONS):
                        all_files.append(os.path.join(root, file))
            
            # Process each file
            for i, file_path in enumerate(all_files):
                try:
                    # Get model info
                    model_info = {
                        "path": file_path,
                        "name": os.path.basename(file_path),
                        "size": os.path.getsize(file_path),
                        "type": os.path.splitext(file_path)[1][1:],  # Extension without dot
                    }
                    models.append(model_info)
                    
                except Exception as e:
                    errors.append({
                        "path": file_path,
                        "error": str(e)
                    })
                
                if progress_callback:
                    progress_callback(i + 1, len(all_files))
            
            return {
                "success": True,
                "models": models,
                "errors": errors,
                "total": len(all_files)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            } 
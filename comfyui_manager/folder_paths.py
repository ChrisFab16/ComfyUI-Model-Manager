"""Module for handling model paths."""

import os
import folder_paths as comfy_folder_paths

# Re-export ComfyUI's folder paths
folder_names_and_paths = comfy_folder_paths.folder_names_and_paths
supported_pt_extensions = comfy_folder_paths.supported_pt_extensions

def get_folder_paths(folder_name: str) -> list[str]:
    """Get paths for a folder type."""
    try:
        paths, _ = folder_names_and_paths[folder_name]
        return paths
    except KeyError:
        return [] 
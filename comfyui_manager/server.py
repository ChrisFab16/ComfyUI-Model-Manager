@routes.get("/model-manager/preview/{folder}/{path_index}/{filename}")
async def handle_preview(request):
    """Handle preview image/video requests."""
    folder = request.match_info["folder"]
    path_index = int(request.match_info["path_index"])
    filename = request.match_info["filename"]
    
    print(f"[ComfyUI Model Manager] Preview request - folder: {folder}, index: {path_index}, filename: {filename}")
    
    # Get folder paths
    try:
        paths = folder_paths.get_folder_paths(folder)
        if not paths or path_index >= len(paths):
            raise ValueError(f"Invalid path index {path_index} for folder {folder}")
        
        base_path = paths[path_index]
        
        # Look for the model file first
        model_name = os.path.splitext(filename)[0]  # Remove .png extension
        model_found = False
        model_path = None
        
        for ext in folder_paths.supported_pt_extensions:
            test_path = os.path.join(base_path, f"{model_name}{ext}")
            if os.path.exists(test_path):
                model_path = test_path
                model_found = True
                break
        
        if not model_found:
            print(f"[ComfyUI Model Manager] Model not found: {model_name}")
            return web.Response(status=404)
        
        # Now look for the preview file
        preview_path = os.path.join(os.path.dirname(model_path), filename)
        if not os.path.exists(preview_path):
            print(f"[ComfyUI Model Manager] Preview not found: {preview_path}")
            return web.Response(status=404)
        
        return web.FileResponse(preview_path)
        
    except Exception as e:
        print(f"[ComfyUI Model Manager] Failed to get preview: {str(e)}")
        return web.Response(status=404)

@routes.get("/model-manager/assets/{filename}")
async def handle_assets(request):
    """Handle static asset requests."""
    filename = request.match_info["filename"]
    asset_path = os.path.join(os.path.dirname(__file__), "assets", filename)
    
    if not os.path.exists(asset_path):
        return web.Response(status=404)
    
    return web.FileResponse(asset_path) 
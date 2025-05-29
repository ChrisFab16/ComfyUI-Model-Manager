import os
import requests
from PIL import Image
from io import BytesIO

def save_preview_image(model_path: str, image_url: str):
    """Save a preview image for a model."""
    if not os.path.exists(model_path):
        raise RuntimeError(f"Model not found: {model_path}")

    dir_name = os.path.dirname(model_path)
    base_name = os.path.splitext(os.path.basename(model_path))[0]
    preview_file = os.path.join(dir_name, f"{base_name}.preview.png")

    try:
        # Download image from URL
        print(f"Downloading preview from {image_url}")
        response = requests.get(image_url)
        response.raise_for_status()
        
        # Save as PNG format
        print("Saving as PNG format...")
        with Image.open(BytesIO(response.content)) as img:
            # Convert to RGB if image is in RGBA mode
            if img.mode == 'RGBA':
                img = img.convert('RGB')
            img.save(preview_file, "PNG", optimize=True)
        
        print(f"Preview saved to {preview_file}")
        return True
    except Exception as e:
        print(f"Failed to save preview image: {e}")
        return False

def main():
    model_path = os.path.abspath("../../models/loras/doll-likeness-by-edg.safetensors")
    preview_url = "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/687d2ce8-95ed-4755-97f1-fb21b5c3aef0/width=1024/13648968.jpeg"
    
    print(f"Downloading preview for model: {model_path}")
    success = save_preview_image(model_path, preview_url)
    if not success:
        exit(1)

if __name__ == "__main__":
    main() 
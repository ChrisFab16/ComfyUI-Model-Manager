"""Test script for downloading models from CivitAI."""

import os
import json
import requests
import time
import hashlib

def calculate_sha256(file_path):
    """Calculate SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()

def verify_metadata(model_path):
    """Verify model metadata."""
    info_path = model_path + ".info"
    if not os.path.exists(info_path):
        print(f"Metadata file not found: {info_path}")
        return False
        
    try:
        with open(info_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
            
        # Verify basic metadata structure
        required_fields = ["name", "description", "model", "files"]
        for field in required_fields:
            if field not in metadata:
                print(f"Missing required field in metadata: {field}")
                return False
                
        # Verify file hash if available
        if metadata["files"][0].get("hashes", {}).get("SHA256"):
            expected_hash = metadata["files"][0]["hashes"]["SHA256"]
            actual_hash = calculate_sha256(model_path)
            if expected_hash.lower() != actual_hash.lower():
                print(f"Hash mismatch! Expected: {expected_hash}, Got: {actual_hash}")
                return False
                
        # Verify preview image
        preview_path = os.path.splitext(model_path)[0] + ".png"
        if not os.path.exists(preview_path):
            print(f"Preview image not found: {preview_path}")
            return False
            
        print("Metadata verification passed!")
        return True
        
    except Exception as e:
        print(f"Error verifying metadata: {e}")
        return False

def test_model_download():
    """Test downloading a small model from CivitAI."""
    # API endpoint
    base_url = "http://127.0.0.1:8188/model-manager"
    
    # Test with a small model from CivitAI
    model_url = "https://civitai.com/models/42903/edg-bond-doll-likeness"
    
    print("1. Fetching model information...")
    response = requests.get(f"{base_url}/model-info", params={"model-page": model_url})
    if not response.ok:
        print(f"Failed to fetch model info: {response.status_code}")
        return
    
    model_info = response.json()
    if not model_info["success"]:
        print(f"Error fetching model info: {model_info.get('error')}")
        return
        
    model_data = model_info["data"][0]  # Get first version
    print(f"\nModel data: {json.dumps(model_data, indent=2)}")
    
    print("\n2. Creating download task...")
    create_data = {
        "type": "loras",  # Force type to loras
        "pathIndex": 0,
        "filename": f"{model_data['basename']}{model_data['extension']}",
        "downloadUrl": model_data["downloadUrl"],
        "downloadPlatform": model_data["downloadPlatform"],
        "sizeKb": model_data["sizeBytes"] / 1024,  # Convert to KB
        "description": model_data["description"],
        "hash": json.dumps(model_data["hashes"]) if model_data.get("hashes") else None,
        "preview": model_data.get("preview", [])[0] if model_data.get("preview") else None
    }
    print(f"Create data: {json.dumps(create_data, indent=2)}")
    
    response = requests.post(f"{base_url}/model", json=create_data)
    if not response.ok:
        print(f"Failed to create download task: {response.status_code}")
        return
        
    task_info = response.json()
    if not task_info["success"]:
        print(f"Error creating download task: {task_info.get('error')}")
        return
        
    task_id = task_info["data"]["taskId"]
    print(f"\nDownload task created with ID: {task_id}")
    
    print("\n3. Monitoring download progress...")
    while True:
        response = requests.get(f"{base_url}/download/task")
        if not response.ok:
            print(f"Failed to get task status: {response.status_code}")
            break
            
        tasks = response.json()
        if not tasks["success"]:
            print(f"Error getting task status: {tasks.get('error')}")
            break
            
        task = next((t for t in tasks["data"] if t["id"] == task_id), None)
        if not task:
            print("Task not found!")
            break
            
        status = task["status"]
        progress = task["progress"]
        print(f"Status: {status}, Progress: {progress:.1f}%")
        
        if status == "COMPLETED":
            print("\nDownload completed!")
            # Verify the downloaded model
            model_path = os.path.join("models", "loras", f"{model_data['basename']}{model_data['extension']}")
            if os.path.exists(model_path):
                print(f"\nModel downloaded to: {model_path}")
                print("\n4. Verifying metadata...")
                verify_metadata(model_path)
            else:
                print(f"\nError: Model file not found at {model_path}")
            break
            
        elif status == "ERROR":
            print(f"\nDownload failed: {task.get('error')}")
            break
            
        time.sleep(1)

if __name__ == "__main__":
    test_model_download()
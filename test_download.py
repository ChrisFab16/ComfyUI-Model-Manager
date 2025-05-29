"""Test script for downloading models from CivitAI."""

import os
import json
import requests
import time

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
        "hash": json.dumps(model_data["hashes"]) if model_data.get("hashes") else None
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
    print(f"Download task created with ID: {task_id}")
    
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
            print("Task not found")
            break
            
        status = task["status"]
        progress = task["progress"]
        print(f"Download status: {status}, progress: {progress:.1f}%")
        
        if status == "completed":
            print("Download completed!")
            break
            
        if status == "error":
            print(f"Download failed: {task.get('error')}")
            break
            
        time.sleep(1)

if __name__ == "__main__":
    test_model_download()
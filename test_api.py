import requests
import json
import time

def print_json(data):
    print(json.dumps(data, indent=2))

def test_model_manager_apis():
    base_url = "http://127.0.0.1:8188"
    
    # Test 1: Get model folders
    print("\nTesting /model-manager/models")
    response = requests.get(f"{base_url}/model-manager/models")
    if response.status_code == 200:
        print("Success! Model folders:")
        print_json(response.json())
    else:
        print(f"Error: {response.status_code}")
        return

    # Test 2: Get models for each folder
    data = response.json()
    if data["success"] and "data" in data:
        folders = data["data"].keys()
        for folder in folders:
            print(f"\nTesting /model-manager/models/{folder}")
            response = requests.get(f"{base_url}/model-manager/models/{folder}")
            if response.status_code == 200:
                result = response.json()
                if result["success"]:
                    print(f"Success! Models in {folder}:")
                    print(f"Is scanning: {result.get('is_scanning', False)}")
                    print(f"Model count: {len(result.get('data', []))}")
                else:
                    print(f"API Error: {result.get('error')}")
            else:
                print(f"HTTP Error: {response.status_code}")

            # If scanning is in progress, wait and check again
            if response.status_code == 200:
                result = response.json()
                if result.get("is_scanning", False):
                    print("Waiting for scan to complete...")
                    time.sleep(2)  # Wait 2 seconds
                    response = requests.get(f"{base_url}/model-manager/models/{folder}")
                    if response.status_code == 200:
                        result = response.json()
                        print(f"Updated model count: {len(result.get('data', []))}")

    # Test 3: Check WebSocket status
    print("\nTesting /model-manager/websocket/status")
    response = requests.get(f"{base_url}/model-manager/websocket/status")
    if response.status_code == 200:
        print("WebSocket status:")
        print_json(response.json())
    else:
        print(f"Error: {response.status_code}")

if __name__ == "__main__":
    test_model_manager_apis() 
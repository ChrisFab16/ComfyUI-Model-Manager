"""Simple direct test of the download API for the Civitai model."""

import requests
import json

def test_model_info():
    """Test getting model info from the API."""
    print("🔍 Testing model info API...")
    
    model_url = "https://civitai.com/models/42903/doll-likeness-by-edg"
    api_url = f"http://127.0.0.1:8188/model-manager/model-info?model-page={model_url}"
    
    try:
        response = requests.get(api_url, timeout=30)
        print(f"Status: {response.status_code}")
        
        if response.ok:
            data = response.json()
            if data.get("success"):
                models = data.get("data", [])
                print(f"✅ Found {len(models)} model versions")
                if models:
                    model = models[0]  # Get first version
                    print(f"Model: {model.get('basename')}{model.get('extension')}")
                    print(f"Size: {model.get('sizeBytes')} bytes")
                    print(f"Download URL: {model.get('downloadUrl')}")
                    return model
            else:
                print(f"❌ API error: {data.get('error')}")
        else:
            print(f"❌ HTTP error: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ Exception: {e}")
    
    return None

def test_download(model_info):
    """Test direct download API call."""
    print("\n🚀 Testing download API...")
    
    if not model_info:
        print("❌ No model info to test with")
        return
    
    # Create minimal download request
    download_data = {
        "downloadUrl": model_info["downloadUrl"],
        "type": "loras",
        "pathIndex": 0,
        "filename": f"{model_info['basename']}{model_info['extension']}",
        "downloadPlatform": "civitai",
        "sizeKb": int(model_info["sizeBytes"] / 1024),
        "description": model_info.get("description", ""),
        "hash": model_info.get("hashes", {}).get("SHA256", "")
    }
    
    print("Request data:")
    print(json.dumps(download_data, indent=2))
    
    try:
        response = requests.post(
            "http://127.0.0.1:8188/model-manager/model",
            json=download_data,
            timeout=30
        )
        
        print(f"\nStatus: {response.status_code}")
        
        if response.ok:
            result = response.json()
            print("Response:")
            print(json.dumps(result, indent=2))
            
            if result.get("success"):
                print("✅ Download task created successfully!")
                return result.get("data", {}).get("taskId")
            else:
                print(f"❌ Download failed: {result.get('error')}")
        else:
            print(f"❌ HTTP error: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ Exception: {e}")
    
    return None

def main():
    """Main test function."""
    print("🧪 Direct Download API Test")
    print("=" * 50)
    
    # Test model info first
    model_info = test_model_info()
    
    if model_info:
        # Test download
        task_id = test_download(model_info)
        
        if task_id:
            print(f"\n✅ Test completed successfully! Task ID: {task_id}")
        else:
            print("\n❌ Download test failed")
    else:
        print("\n❌ Model info test failed")

if __name__ == "__main__":
    main() 
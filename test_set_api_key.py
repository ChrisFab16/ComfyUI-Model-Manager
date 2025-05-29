"""Test script to set API keys for model downloads."""

import requests
import base64
import json

def set_api_key(key: str, value: str):
    """Set an API key."""
    # Encode the API key in base64
    encoded_value = base64.b64encode(value.encode("utf-8")).decode("utf-8")
    
    # Send request to set the key
    response = requests.post(
        "http://127.0.0.1:8188/api/model-manager/download/setting",
        json={"key": key, "value": encoded_value}
    )
    return response.json()

def main():
    """Main function."""
    # Initialize download settings first
    print("\nInitializing download settings...")
    init_response = requests.post("http://127.0.0.1:8188/api/model-manager/download/init")
    if not init_response.ok:
        print(f"Failed to initialize download settings: {init_response.status_code}")
        return
    
    # Get API key from environment or user input
    import os
    civitai_key = os.environ.get("CIVITAI_API_KEY")
    if not civitai_key:
        civitai_key = input("Enter your Civitai API key: ")
    
    # Set the API key
    print("\nSetting Civitai API key...")
    result = set_api_key("civitai", civitai_key)
    if result.get("success", False):
        print("Successfully set Civitai API key")
    else:
        print(f"Failed to set API key: {result.get('error', 'Unknown error')}")

if __name__ == "__main__":
    main() 
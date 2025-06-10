#!/usr/bin/env python3
"""Test script to check download system status and API configuration."""

import requests
import json
import time

def test_download_system():
    """Test the download system components."""
    print("🔍 Testing Download System Status")
    print("=" * 50)
    
    # Test API key status
    print('\n1. Testing API key initialization...')
    try:
        response = requests.post('http://127.0.0.1:8188/model-manager/download/init')
        if response.ok:
            print('✅ Download system initialized')
            data = response.json()
            if data.get('success'):
                api_data = data.get('data', {})
                print(f'✅ API keys configured: {list(api_data.keys())}')
                for key, value in api_data.items():
                    print(f'   {key}: {value}')
            else:
                print('❌ Download system failed to initialize')
        else:
            print(f'❌ Failed to initialize download system: {response.status_code}')
    except Exception as e:
        print(f'❌ Error testing download system: {e}')

    # Test model folders
    print('\n2. Testing model folders...')
    try:
        response = requests.get('http://127.0.0.1:8188/model-manager/models')
        if response.ok:
            data = response.json()
            if data.get('success'):
                folders = data.get('data', {})
                print(f'✅ Found {len(folders)} model folder types: {list(folders.keys())}')
                
                # Test loras specifically
                if 'loras' in folders:
                    print('\n   Testing LoRA models...')
                    response = requests.get('http://127.0.0.1:8188/model-manager/models/loras')
                    if response.ok:
                        lora_data = response.json()
                        if lora_data.get('success'):
                            models = lora_data.get('data', [])
                            is_scanning = lora_data.get('is_scanning', False)
                            print(f'   📁 LoRA models: {len(models)} found, scanning: {is_scanning}')
                            
                            # If scanning, wait and check again
                            if is_scanning and len(models) == 0:
                                print('   ⏳ Waiting for scan to complete...')
                                time.sleep(3)
                                response = requests.get('http://127.0.0.1:8188/model-manager/models/loras')
                                if response.ok:
                                    lora_data = response.json()
                                    models = lora_data.get('data', [])
                                    print(f'   📁 LoRA models after scan: {len(models)} found')
                            
                            # Analyze metadata completeness
                            if models:
                                complete_metadata = 0
                                has_preview = 0
                                
                                for model in models:
                                    metadata = model.get('metadata', {})
                                    if metadata and len(metadata) > 5:  # Basic threshold for complete metadata
                                        complete_metadata += 1
                                    if model.get('preview'):
                                        has_preview += 1
                                
                                print(f'   📊 Models with complete metadata: {complete_metadata}/{len(models)}')
                                print(f'   🖼️  Models with previews: {has_preview}/{len(models)}')
                                
                                # Sample model analysis
                                print(f'\n   Sample model analysis:')
                                model = models[0]
                                print(f'   📄 Filename: {model.get("filename", "unknown")}')
                                print(f'   📊 Metadata keys: {list(model.get("metadata", {}).keys())}')
                                print(f'   🖼️  Preview: {bool(model.get("preview"))}')
                                print(f'   📏 Size: {model.get("size", 0)} bytes')
                                print(f'   🔗 Model type: {model.get("model_type", "unknown")}')
                                print(f'   📝 Description: {len(model.get("description", ""))} chars')
                        else:
                            print(f'   ❌ LoRA listing failed: {lora_data.get("error")}')
                    else:
                        print(f'   ❌ Failed to list LoRA models: {response.status_code}')
            else:
                print(f'❌ Model folders failed: {data.get("error")}')
        else:
            print(f'❌ Failed to get model folders: {response.status_code}')
    except Exception as e:
        print(f'❌ Error testing model folders: {e}')

    # Test download tasks
    print('\n3. Testing download task system...')
    try:
        response = requests.get('http://127.0.0.1:8188/model-manager/download/task')
        if response.ok:
            data = response.json()
            if data.get('success'):
                tasks = data.get('data', [])
                print(f'✅ Download task system working')
                print(f'   Active tasks: {len(tasks)}')
                
                for task in tasks:
                    print(f'   📋 Task {task.get("id", "unknown")}: {task.get("status", "unknown")} ({task.get("progress", 0):.1f}%)')
            else:
                print(f'❌ Task system failed: {data.get("error")}')
        else:
            print(f'❌ Failed to access task system: {response.status_code}')
    except Exception as e:
        print(f'❌ Error testing task system: {e}')

    # Test model info fetching capability
    print('\n4. Testing model info API...')
    try:
        # Test with a sample CivitAI URL
        test_url = "https://civitai.com/models/42903/edg-bond-doll-likeness"
        response = requests.get('http://127.0.0.1:8188/model-manager/model-info', params={"model-page": test_url})
        if response.ok:
            data = response.json()
            if data.get('success'):
                model_info = data.get('data', [])
                print(f'✅ Model info fetching works: {len(model_info)} versions found')
                if model_info:
                    sample = model_info[0]
                    print(f'   📦 Sample model: {sample.get("basename", "unknown")}')
                    print(f'   🔗 Download URL: {bool(sample.get("downloadUrl"))}')
                    print(f'   📝 Description: {len(sample.get("description", ""))} chars')
            else:
                print(f'❌ Model info failed: {data.get("error")}')
        else:
            print(f'❌ Failed to fetch model info: {response.status_code}')
    except Exception as e:
        print(f'❌ Error testing model info: {e}')

    print('\n' + '=' * 50)
    print('📋 Test Complete')

if __name__ == "__main__":
    test_download_system() 
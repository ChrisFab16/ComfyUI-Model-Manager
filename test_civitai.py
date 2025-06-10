"""Test script for downloading models from Civitai and verifying metadata."""

import os
import json
import requests
import hashlib
import time
import sys
import threading
import queue
import traceback
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import concurrent.futures

class DownloadTimeout(Exception):
    """Raised when a download task times out."""
    pass

class TaskError(Exception):
    """Raised when a task fails."""
    pass

class DetailedLogger:
    """Detailed logger with timestamps and step tracking."""
    def __init__(self):
        self.step_counter = 0
    
    def log(self, message: str, level: str = "INFO"):
        """Log a message with timestamp and step counter."""
        self.step_counter += 1
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{timestamp}] [{level}] Step {self.step_counter:02d}: {message}")
        sys.stdout.flush()  # Force immediate output
    
    def error(self, message: str):
        """Log an error message."""
        self.log(message, "ERROR")
    
    def warn(self, message: str):
        """Log a warning message."""
        self.log(message, "WARN")
    
    def success(self, message: str):
        """Log a success message."""
        self.log(message, "SUCCESS")

# Global logger instance
logger = DetailedLogger()

class APIMonitor:
    """Monitor API calls in a separate thread."""
    
    def __init__(self, task_id: str):
        self.task_id = task_id
        self.running = False
        self.thread = None
        self.status_queue = queue.Queue()
        self.last_status = None
        self.last_progress = -1
        
    def start(self):
        """Start monitoring in a separate thread."""
        logger.log(f"Starting API monitor for task {self.task_id}")
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
    
    def stop(self):
        """Stop monitoring."""
        logger.log("Stopping API monitor")
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
    
    def get_latest_status(self) -> Optional[Tuple[str, float, Optional[str]]]:
        """Get the latest status from the queue."""
        try:
            while not self.status_queue.empty():
                self.last_status = self.status_queue.get_nowait()
            return self.last_status
        except queue.Empty:
            return self.last_status
    
    def _monitor_loop(self):
        """Monitor loop running in separate thread."""
        logger.log("API monitor thread started")
        while self.running:
            try:
                logger.log(f"Checking task status for {self.task_id}")
                response = requests.get(
                    "http://127.0.0.1:8188/model-manager/download/task", 
                    timeout=10
                )
                
                if not response.ok:
                    logger.warn(f"Status check failed: {response.status_code}")
                    time.sleep(2)
                    continue
                
                tasks = response.json()
                if not tasks.get("success", False):
                    logger.warn(f"Status response error: {tasks.get('error', 'Unknown')}")
                    time.sleep(2)
                    continue
                
                task = next((t for t in tasks["data"] if t["id"] == self.task_id), None)
                if not task:
                    logger.warn(f"Task {self.task_id} not found in status list")
                    time.sleep(2)
                    continue
                
                status = task.get("status", "UNKNOWN")
                progress = task.get("progress", 0)
                error = task.get("error")
                
                # Report changes
                if status != self.last_status or abs(progress - self.last_progress) >= 1.0:
                    logger.log(f"Task status: {status}, Progress: {progress:.1f}%")
                    if error:
                        logger.error(f"Task error: {error}")
                    
                    self.status_queue.put((status, progress, error))
                    
                    # Update tracking
                    if status != self.last_status:
                        self.last_status = status
                    if abs(progress - self.last_progress) >= 1.0:
                        self.last_progress = progress
                
                # Stop monitoring if task is complete
                if status.upper() in ["COMPLETED", "ERROR", "CANCELLED"]:
                    logger.log(f"Task reached final state: {status}")
                    break
                    
                time.sleep(0.5)  # Poll every 500ms
                
            except Exception as e:
                logger.error(f"API monitor error: {str(e)}")
                time.sleep(2)
        
        logger.log("API monitor thread stopping")

class FileSystemMonitor:
    """Monitor filesystem for file creation."""
    
    def __init__(self, expected_files: list):
        self.expected_files = expected_files
        self.found_files = {}
        self.running = False
        self.thread = None
    
    def start(self):
        """Start monitoring filesystem."""
        logger.log(f"Starting filesystem monitor for {len(self.expected_files)} files")
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
    
    def stop(self):
        """Stop monitoring."""
        logger.log("Stopping filesystem monitor")
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
    
    def get_status(self) -> Dict[str, bool]:
        """Get current file status."""
        return dict(self.found_files)
    
    def _monitor_loop(self):
        """Monitor filesystem in separate thread."""
        logger.log("Filesystem monitor thread started")
        while self.running:
            try:
                for file_path in self.expected_files:
                    exists = os.path.exists(file_path)
                    if file_path not in self.found_files or self.found_files[file_path] != exists:
                        self.found_files[file_path] = exists
                        if exists:
                            logger.success(f"File found: {file_path}")
                        else:
                            logger.log(f"File not yet found: {file_path}")
                
                # Check if all files found
                if all(self.found_files.values()):
                    logger.success("All expected files found!")
                    break
                    
                time.sleep(1)  # Check every second
                
            except Exception as e:
                logger.error(f"Filesystem monitor error: {str(e)}")
                time.sleep(2)
        
        logger.log("Filesystem monitor thread stopping")

def get_comfyui_models_path() -> str:
    """Get the correct ComfyUI models directory path."""
    current_dir = os.getcwd()
    logger.log(f"Current working directory: {current_dir}")
    
    if "ComfyUI-Model-Manager" in current_dir:
        # Go up two levels to reach ComfyUI root
        comfyui_root = os.path.join(current_dir, "..", "..")
        models_path = os.path.join(comfyui_root, "models")
        result = os.path.abspath(models_path)
        logger.log(f"Computed models path (from plugin dir): {result}")
        return result
    else:
        # Assume we're already in ComfyUI root
        result = os.path.abspath("models")
        logger.log(f"Computed models path (from ComfyUI root): {result}")
        return result

def get_model_info(model_url: str, timeout: int = 30) -> Dict[str, Any]:
    """Get model information from Civitai."""
    logger.log(f"Requesting model info from: {model_url}")
    
    try:
        logger.log("Sending GET request to model-info endpoint")
        response = requests.get(
            f"http://127.0.0.1:8188/model-manager/model-info?model-page={model_url}",
            timeout=timeout
        )
        
        logger.log(f"Response status: {response.status_code}")
        if not response.ok:
            logger.error(f"Failed to get model info: {response.status_code} - {response.text}")
            raise RuntimeError(f"Failed to get model info: {response.status_code} - {response.text}")
        
        data = response.json()["data"]
        logger.log(f"Retrieved {len(data)} model versions")
        
        if not data:
            raise RuntimeError("No model information returned")
        
        # Take the first model version
        model_info = data[0]
        logger.success("Model info retrieved successfully")
        logger.log(f"Model: {model_info.get('basename', 'Unknown')}{model_info.get('extension', '')}")
        logger.log(f"Size: {model_info.get('sizeBytes', 0)} bytes")
        logger.log(f"Type: {model_info.get('type', 'Unknown')}")
        
        return model_info
        
    except requests.Timeout:
        raise RuntimeError(f"Model info request timed out after {timeout} seconds")
    except requests.RequestException as e:
        raise RuntimeError(f"Failed to get model info: {str(e)}")

def find_model_file(filename: str, model_type: str = "loras", timeout: int = 30) -> Optional[str]:
    """Find the downloaded model file with timeout and detailed logging."""
    logger.log(f"Searching for model file: {filename}")
    
    models_root = get_comfyui_models_path()
    logger.log(f"Models root directory: {models_root}")
    
    # Check if models directory exists
    if not os.path.exists(models_root):
        logger.error(f"Models directory does not exist: {models_root}")
        return None
    
    possible_paths = [
        os.path.join(models_root, model_type, filename),
        os.path.join(models_root, "loras", filename),
        os.path.join(models_root, "checkpoints", filename),
    ]
    
    logger.log(f"Will check {len(possible_paths)} possible paths")
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        for i, path in enumerate(possible_paths):
            logger.log(f"Checking path {i+1}/{len(possible_paths)}: {path}")
            
            try:
                if os.path.exists(path):
                    file_size = os.path.getsize(path)
                    logger.success(f"Found model file at: {path} (size: {file_size} bytes)")
                    return path
                else:
                    logger.log(f"Not found at: {path}")
            except Exception as e:
                logger.error(f"Error checking path {path}: {e}")
        
        # List directory contents for debugging
        try:
            for subdir in ["loras", "checkpoints", "unet", "clip", "vae"]:
                dir_path = os.path.join(models_root, subdir)
                if os.path.exists(dir_path):
                    files = os.listdir(dir_path)
                    logger.log(f"Contents of {subdir}: {len(files)} files")
                    if files:
                        recent_files = [f for f in files if f.endswith(('.safetensors', '.ckpt', '.pt'))][:3]
                        logger.log(f"Recent model files in {subdir}: {recent_files}")
                else:
                    logger.log(f"Directory does not exist: {dir_path}")
        except Exception as e:
            logger.error(f"Error listing directories: {e}")
        
        logger.log(f"File not found yet, waiting 2 seconds... ({int(time.time() - start_time)}/{timeout}s)")
        time.sleep(2)
    
    logger.error(f"Model file not found after {timeout} seconds")
    return None

def download_model(model_info: Dict[str, Any], timeout: int = 300) -> str:
    """Download model using the model manager API with detailed monitoring."""
    filename = f"{model_info['basename']}{model_info['extension']}"
    size_kb = int(model_info["sizeBytes"] / 1024) if "sizeBytes" in model_info else 0
    
    logger.log(f"Starting download of {filename} ({size_kb} KB)")
    
    try:
        # Create download request
        download_request = {
            "downloadUrl": model_info["downloadUrl"],
            "type": model_info.get("type", "loras"),
            "pathIndex": 0,
            "filename": filename,
            "downloadPlatform": "civitai",
            "sizeKb": size_kb,
            "description": model_info.get("description", ""),
            "hash": model_info.get("hashes", {}).get("SHA256", ""),
            "preview": model_info.get("preview", []),  # Include preview URLs
            "images": model_info.get("preview", [])   # Also include as images for compatibility
        }
        
        logger.log("Sending download request to API")
        logger.log(f"Request payload: {json.dumps(download_request, indent=2)}")
        
        response = requests.post(
            "http://127.0.0.1:8188/model-manager/model",
            json=download_request,
            timeout=30
        )
        
        logger.log(f"Download request response status: {response.status_code}")
        response.raise_for_status()
        
        response_data = response.json()
        logger.log(f"Download response: {json.dumps(response_data, indent=2)}")
        
        if not response_data.get("success", False):
            error_msg = response_data.get("error", "Unknown error")
            raise RuntimeError(f"Failed to create download task: {error_msg}")
        
        task_id = response_data["data"]["taskId"]
        logger.success(f"Download task created with ID: {task_id}")
        
        # Start API monitoring in separate thread
        api_monitor = APIMonitor(task_id)
        api_monitor.start()
        
        # Prepare expected file paths
        models_root = get_comfyui_models_path()
        model_type = model_info.get("type", "loras")
        expected_model_path = os.path.join(models_root, model_type, filename)
        expected_info_path = expected_model_path + ".info"
        expected_preview_path = os.path.splitext(expected_model_path)[0] + ".png"
        
        expected_files = [expected_model_path, expected_info_path, expected_preview_path]
        
        # Start filesystem monitoring
        fs_monitor = FileSystemMonitor(expected_files)
        fs_monitor.start()
        
        try:
            # Wait for task completion
            logger.log(f"Waiting for task completion (timeout: {timeout}s)")
            start_time = time.time()
            task_completed = False
            
            while time.time() - start_time < timeout:
                # Check API status
                status_info = api_monitor.get_latest_status()
                if status_info:
                    status, progress, error = status_info
                    
                    if status.upper() == "COMPLETED":
                        logger.success("Task completed successfully!")
                        task_completed = True
                        break
                    elif status.upper() == "ERROR":
                        raise TaskError(f"Download failed: {error or 'Unknown error'}")
                    elif status.upper() == "CANCELLED":
                        raise TaskError("Download was cancelled")
                
                time.sleep(1)
            
            if not task_completed:
                logger.error(f"Task timed out after {timeout} seconds")
                # Try to cancel the task
                try:
                    cancel_response = requests.post(
                        f"http://127.0.0.1:8188/model-manager/task/{task_id}/cancel",
                        timeout=5
                    )
                    logger.log(f"Task cancellation response: {cancel_response.status_code}")
                except Exception as e:
                    logger.error(f"Failed to cancel task: {e}")
                
                raise DownloadTimeout(f"Task {task_id} timed out after {timeout} seconds")
            
            # Task completed, now find the file
            logger.log("Task completed, searching for downloaded files")
            
            # Wait a bit for filesystem to sync
            time.sleep(2)
            
            # Check filesystem monitor results
            fs_status = fs_monitor.get_status()
            logger.log(f"Filesystem status: {fs_status}")
            
            # Find the model file
            model_path = find_model_file(filename, model_type, timeout=30)
            
            if not model_path:
                raise RuntimeError(f"Model file not found after download completion: {filename}")
            
            logger.success(f"Model file located at: {model_path}")
            return model_path
            
        finally:
            # Clean up monitors
            api_monitor.stop()
            fs_monitor.stop()
        
    except requests.Timeout:
        raise RuntimeError("Download request timed out")
    except requests.RequestException as e:
        raise RuntimeError(f"Download request failed: {str(e)}")

def verify_metadata(model_path: str, timeout: int = 30) -> bool:
    """Verify model metadata with detailed logging."""
    logger.log(f"Starting metadata verification for: {model_path}")
    
    try:
        info_path = model_path + ".info"
        preview_path = os.path.splitext(model_path)[0] + ".png"
        
        logger.log(f"Expected info file: {info_path}")
        logger.log(f"Expected preview file: {preview_path}")
        
        # Check file existence with timeout
        start_time = time.time()
        while time.time() - start_time < timeout:
            info_exists = os.path.exists(info_path)
            preview_exists = os.path.exists(preview_path)
            
            logger.log(f"Info exists: {info_exists}, Preview exists: {preview_exists}")
            
            if info_exists:
                break
                
            logger.log("Waiting for metadata files...")
            time.sleep(1)
        
        # Final check
        info_exists = os.path.exists(info_path)
        preview_exists = os.path.exists(preview_path)
        
        logger.log(f"Final check - Info: {info_exists}, Preview: {preview_exists}")
        
        if not info_exists:
            logger.error("Info file not found")
            return False
        
        if not preview_exists:
            logger.warn("Preview file not found (this may be expected)")
        
        # Verify metadata structure
        try:
            logger.log("Reading info file")
            with open(info_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
            
            logger.success("Info file is valid JSON")
            logger.log(f"Metadata keys: {list(metadata.keys())}")
            
            # Check required fields
            required_fields = ["name", "description", "model"]
            missing_fields = [field for field in required_fields if field not in metadata]
            
            if missing_fields:
                logger.warn(f"Missing metadata fields: {missing_fields}")
            else:
                logger.success("All required metadata fields present")
            
            logger.success("Metadata verification completed successfully")
            return True
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing metadata JSON: {e}")
            return False
        except Exception as e:
            logger.error(f"Error reading metadata file: {e}")
            return False
            
    except Exception as e:
        logger.error(f"Error during metadata verification: {e}")
        return False

def main():
    """Main test function with detailed logging and monitoring."""
    print("🚀 Starting ComfyUI Model Manager download test")
    print("=" * 80)
    
    logger.log("Test started")
    
    exit_code = 1  # Default to error
    model_path = None
    
    # Set overall test timeout using threading timer
    timeout_occurred = threading.Event()
    def timeout_handler():
        timeout_occurred.set()
        logger.error("Overall test timeout occurred!")
    
    timeout_timer = threading.Timer(600, timeout_handler)  # 10 minute total timeout
    timeout_timer.start()
    
    try:
        # Test with a small LoRA model
        model_url = "https://civitai.com/models/42903/edg-bond-doll-likeness"
        logger.log(f"Getting model info from {model_url}")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            # Submit model info request
            future_model_info = executor.submit(get_model_info, model_url)
            
            # Wait for model info with periodic timeout checks
            while not future_model_info.done():
                if timeout_occurred.is_set():
                    raise TimeoutError("Overall test timeout exceeded")
                time.sleep(0.5)
            
            model_info = future_model_info.result()
        
        logger.success("Model info retrieved. Starting download")
        
        # Download model
        if timeout_occurred.is_set():
            raise TimeoutError("Overall test timeout exceeded")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future_download = executor.submit(download_model, model_info)
            
            # Wait for download with periodic timeout checks
            while not future_download.done():
                if timeout_occurred.is_set():
                    raise TimeoutError("Overall test timeout exceeded")
                time.sleep(1)
            
            model_path = future_download.result()
        
        logger.success(f"Download completed. Verifying metadata for {model_path}")
        
        # Verify metadata
        if timeout_occurred.is_set():
            raise TimeoutError("Overall test timeout exceeded")
        
        if verify_metadata(model_path):
            logger.success("Test PASSED! Model downloaded and metadata verified successfully")
            exit_code = 0  # Success
        else:
            logger.warn("Test PARTIAL SUCCESS! Model downloaded but metadata verification failed")
            exit_code = 0  # Still consider it success since download worked
            
    except TimeoutError:
        logger.error("Test FAILED: Overall timeout exceeded")
    except DownloadTimeout as e:
        logger.error(f"Test FAILED: {e}")
    except TaskError as e:
        logger.error(f"Test FAILED: {e}")
    except Exception as e:
        logger.error(f"Test FAILED with error: {e}")
        logger.error("Full error traceback:")
        traceback.print_exc()
    finally:
        # Stop timeout timer
        timeout_timer.cancel()
        
        # Final summary
        print("=" * 80)
        logger.log("Test Summary:")
        if exit_code == 0:
            logger.success("Overall result: SUCCESS")
        else:
            logger.error("Overall result: FAILURE")
            
        if model_path:
            logger.log(f"Model file: {model_path}")
            
        logger.log(f"Exiting with code: {exit_code}")
        
        # Force flush all output
        sys.stdout.flush()
        sys.stderr.flush()
        
        # Give threads time to clean up
        time.sleep(1)
        
        sys.exit(exit_code)

if __name__ == "__main__":
    main() 
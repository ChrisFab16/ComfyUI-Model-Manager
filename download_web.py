import os
import json
import yaml
import shutil
import tarfile
import requests

def normalize_path(path: str):
    return path.replace(os.path.sep, "/")

def join_path(path: str, *paths: list[str]):
    return normalize_path(os.path.join(path, *paths))

def get_current_version():
    try:
        pyproject_path = join_path(os.path.dirname(__file__), "pyproject.toml")
        with open(pyproject_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("version"):
                    return line.split("=")[1].strip().strip('"').strip("'")
    except:
        return "0.0.0"

def download_web_distribution(version: str):
    extension_uri = os.path.dirname(__file__)
    web_path = join_path(extension_uri, "web")
    
    print(f"Downloading web distribution version {version}...")
    download_url = f"https://github.com/hayden-fr/ComfyUI-Model-Manager/releases/download/v{version}/dist.tar.gz"
    response = requests.get(download_url, stream=True)
    response.raise_for_status()

    temp_file = join_path(extension_uri, "temp.tar.gz")
    with open(temp_file, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    if os.path.exists(web_path):
        shutil.rmtree(web_path)

    print("Extracting web distribution...")
    with tarfile.open(temp_file, "r:gz") as tar:
        members = [member for member in tar.getmembers() if member.name.startswith("web/")]
        tar.extractall(path=extension_uri, members=members)

    os.remove(temp_file)
    print("Web distribution downloaded successfully.")

if __name__ == "__main__":
    version = get_current_version()
    print(f"Current version: {version}")
    download_web_distribution(version) 
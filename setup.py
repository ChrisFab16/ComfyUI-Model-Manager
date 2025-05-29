from setuptools import setup, find_packages

setup(
    name="comfyui-model-manager",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "aiohttp>=3.8.0",
        "fastapi>=0.68.0",
        "pytest>=7.0.0",
        "pytest-asyncio>=0.20.0",
        "watchdog>=2.1.0",
        "uvicorn>=0.15.0"
    ],
) 
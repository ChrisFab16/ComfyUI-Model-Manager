"""Tests for task handlers."""

import os
import tempfile
import unittest
import asyncio
import aiohttp
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from comfyui_manager.task_system.tasks import (
    DownloadModelTask,
    ScanModelTask,
    MetadataTask
)

class MockResponse:
    """Mock aiohttp response."""
    
    def __init__(self, content):
        self.status = 200
        self.headers = {'content-length': str(len(content))}
        self._content = content

    @property
    def content(self):
        return self

    async def iter_chunked(self, chunk_size):
        yield self._content

class MockSession:
    """Mock aiohttp ClientSession."""
    
    def __init__(self, response):
        self._response = response

    async def get(self, url):
        return self._response

    async def close(self):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None

class TestTaskHandlers(unittest.IsolatedAsyncioTestCase):
    """Test cases for task handlers."""

    async def asyncSetUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.download_dir = os.path.join(self.temp_dir, 'models')
        self.metadata_dir = os.path.join(self.temp_dir, 'metadata')
        os.makedirs(self.download_dir, exist_ok=True)
        os.makedirs(self.metadata_dir, exist_ok=True)

    async def asyncTearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir)

    async def test_download_task(self):
        """Test download task handler."""
        # Create a mock progress reporter
        progress = AsyncMock()

        # Create test file content
        test_content = b"test model content"
        
        # Create mock response and session
        mock_response = MockResponse(test_content)
        mock_session = MockSession(mock_response)

        # Create task handler
        handler = DownloadModelTask(self.download_dir)
        
        # Create test task
        task = {
            'params': {
                'url': 'http://test.com/model.safetensors',
                'model_type': 'checkpoints'
            }
        }

        # Execute task with mock session
        result = await handler(task, progress, mock_session)

        self.assertTrue(result['success'])
        self.assertTrue(os.path.exists(result['file_path']))
        self.assertEqual(result['model_type'], 'checkpoints')

    async def test_scan_task(self):
        """Test scan task handler."""
        # Create mock progress reporter
        progress = AsyncMock()

        # Create some test model files
        model_types = ['checkpoints', 'loras', 'embeddings']
        created_files = []
        
        for model_type in model_types:
            type_dir = os.path.join(self.download_dir, model_type)
            os.makedirs(type_dir, exist_ok=True)
            
            # Create a test file
            test_file = os.path.join(type_dir, f'test_{model_type}.safetensors')
            with open(test_file, 'wb') as f:
                f.write(b'test content')
            created_files.append(test_file)

        # Create task handler
        handler = ScanModelTask([self.download_dir])
        
        # Create test task
        task = {'params': {}}

        # Execute task
        result = await handler(task, progress)

        self.assertTrue(result['success'])
        self.assertEqual(result['total_count'], len(created_files))
        
        # Verify all test files were found
        found_paths = [m['path'] for m in result['models']]
        for test_file in created_files:
            self.assertIn(test_file, found_paths)

    async def test_metadata_task(self):
        """Test metadata task handler."""
        # Create mock progress reporter
        progress = AsyncMock()

        # Create a test model file
        model_dir = os.path.join(self.download_dir, 'checkpoints')
        test_model = os.path.join(model_dir, 'test_model.safetensors')
        os.makedirs(model_dir, exist_ok=True)
        
        with open(test_model, 'wb') as f:
            f.write(b'test model content')

        # Create task handler
        handler = MetadataTask(self.metadata_dir)
        
        # Create test task
        task = {
            'params': {
                'model_path': test_model
            }
        }

        # Execute task
        result = await handler(task, progress)

        self.assertTrue(result['success'])
        self.assertTrue(os.path.exists(result['metadata_path']))
        
        # Verify metadata content
        metadata = result['metadata']
        self.assertEqual(metadata['filename'], 'test_model.safetensors')
        self.assertEqual(metadata['path'], test_model)
        self.assertEqual(metadata['type'], 'checkpoints')
        self.assertIsNotNone(metadata['hash'])

if __name__ == '__main__':
    unittest.main() 
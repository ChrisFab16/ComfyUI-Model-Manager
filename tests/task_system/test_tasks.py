"""Tests for the task management system."""

import asyncio
import unittest
import sys
import os
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from comfyui_manager.task_system.task_queue import Task, TaskStatus, TaskQueue
from comfyui_manager.task_system.task_worker import TaskWorker, ProgressReporter
from comfyui_manager.task_system.task_manager import TaskManager

class TestTaskSystem(unittest.IsolatedAsyncioTestCase):
    """Test cases for the task management system."""

    async def test_task_queue(self):
        """Test basic task queue functionality."""
        logger.info("Starting task queue test")
        queue = TaskQueue(max_concurrent=2)
        await queue.start()

        # Add tasks
        logger.debug("Adding tasks to queue")
        task1 = await queue.add_task("test", {"value": 1})
        task2 = await queue.add_task("test", {"value": 2})
        task3 = await queue.add_task("test", {"value": 3})

        self.assertEqual(len(queue.tasks), 3)
        self.assertEqual(task1.status, TaskStatus.PENDING)
        logger.debug(f"Task1 status: {task1.status}, Task2 status: {task2.status}, Task3 status: {task3.status}")

        # Wait for tasks to process
        await asyncio.sleep(0.1)  # Reduced sleep time for faster tests

        # Stop queue
        logger.info("Stopping task queue")
        await queue.stop()

    async def test_task_worker(self):
        """Test task worker with custom handler."""
        logger.info("Starting task worker test")
        worker = TaskWorker()

        async def test_handler(task):
            logger.debug(f"Test handler executing for task {task.id}")
            return {"result": task.params["value"] * 2}

        worker.register_handler("test", test_handler)

        task = Task("test", {"value": 5})
        logger.debug(f"Created task {task.id} with value 5")
        result = await worker.execute(task)

        self.assertEqual(result["result"], 10)
        self.assertEqual(task.status, TaskStatus.COMPLETED)
        logger.debug(f"Task {task.id} completed with result {result}")

    async def test_task_manager(self):
        """Test task manager functionality."""
        logger.info("Starting task manager test")
        manager = TaskManager()

        # Mock WebSocket client
        class MockWebSocket:
            def __init__(self):
                self.messages = []

            async def send_json(self, message):
                logger.debug(f"WebSocket received message: {message}")
                self.messages.append(message)

        # Register mock client
        mock_client = MockWebSocket()
        manager.register_websocket(mock_client)
        logger.debug("Registered mock WebSocket client")

        await manager.start()
        logger.debug("Task manager started")

        # Create and monitor task
        task = await manager.create_task("download_model", {
            "url": "test_url",
            "model_type": "test"
        })
        logger.debug(f"Created task {task.id}")

        # Wait for task to process
        logger.debug("Waiting for task to process")
        await asyncio.sleep(0.5)  # Wait for progress updates

        # Log received messages
        logger.debug(f"Received {len(mock_client.messages)} WebSocket messages:")
        for msg in mock_client.messages:
            logger.debug(f"Message: {msg}")

        # Verify WebSocket messages
        self.assertTrue(len(mock_client.messages) > 0)
        self.assertTrue(any(m["type"] == "task_created" for m in mock_client.messages))
        self.assertTrue(any(m["type"] == "task_progress" for m in mock_client.messages))

        # Stop manager
        logger.info("Stopping task manager")
        await manager.stop()

if __name__ == '__main__':
    unittest.main() 
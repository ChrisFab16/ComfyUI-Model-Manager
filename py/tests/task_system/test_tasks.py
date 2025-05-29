"""Tests for the task management system."""

import asyncio
import pytest

from comfyui_manager.task_system.task_queue import Task, TaskStatus, TaskQueue
from comfyui_manager.task_system.task_worker import TaskWorker, ProgressReporter
from comfyui_manager.task_system.task_manager import TaskManager

@pytest.mark.asyncio
async def test_task_queue():
    """Test basic task queue functionality."""
    queue = TaskQueue(max_concurrent=2)
    await queue.start()

    # Add tasks
    task1 = await queue.add_task("test", {"value": 1})
    task2 = await queue.add_task("test", {"value": 2})
    task3 = await queue.add_task("test", {"value": 3})

    assert len(queue.tasks) == 3
    assert task1.status == TaskStatus.PENDING

    # Wait for tasks to process
    await asyncio.sleep(0.1)  # Reduced sleep time for faster tests

    # Stop queue
    await queue.stop()

@pytest.mark.asyncio
async def test_task_worker():
    """Test task worker with custom handler."""
    worker = TaskWorker()

    async def test_handler(task):
        return {"result": task.params["value"] * 2}

    worker.register_handler("test", test_handler)

    task = Task("test", {"value": 5})
    result = await worker.execute(task)

    assert result["result"] == 10
    assert task.status == TaskStatus.COMPLETED

@pytest.mark.asyncio
async def test_task_manager():
    """Test task manager functionality."""
    manager = TaskManager()
    await manager.start()

    # Mock WebSocket client
    class MockWebSocket:
        def __init__(self):
            self.messages = []

        async def send_json(self, message):
            self.messages.append(message)

    # Register mock client
    mock_client = MockWebSocket()
    manager.register_websocket(mock_client)

    # Create and monitor task
    task = await manager.create_task("download_model", {
        "url": "test_url",
        "model_type": "test"
    })

    # Wait for task to process
    await asyncio.sleep(0.1)  # Reduced sleep time for faster tests

    # Verify WebSocket messages
    assert len(mock_client.messages) > 0
    assert any(m["type"] == "task_created" for m in mock_client.messages)
    assert any(m["type"] == "task_progress" for m in mock_client.messages)

    # Stop manager
    await manager.stop() 
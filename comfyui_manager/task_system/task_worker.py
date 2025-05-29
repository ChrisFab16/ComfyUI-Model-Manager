from typing import Dict, Any, Callable, Coroutine
import asyncio
from .task_queue import Task, TaskStatus

class TaskWorker:
    def __init__(self):
        self._handlers: Dict[str, Callable[[Task], Coroutine[Any, Any, Any]]] = {}

    def register_handler(self, task_type: str, handler: Callable[[Task], Coroutine[Any, Any, Any]]):
        """Register a handler for a specific task type."""
        self._handlers[task_type] = handler

    async def execute(self, task: Task) -> Any:
        """Execute a task using its registered handler."""
        if task.type not in self._handlers:
            raise ValueError(f"No handler registered for task type: {task.type}")

        handler = self._handlers[task.type]
        try:
            task.status = TaskStatus.RUNNING
            result = await handler(task)
            task.status = TaskStatus.COMPLETED
            task.result = result
            return result
        except asyncio.CancelledError:
            task.status = TaskStatus.CANCELLED
            raise
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            raise

class ProgressReporter:
    def __init__(self, task: Task):
        self.task = task

    def update(self, progress: float, message: str = ""):
        """Update task progress (0-100)."""
        self.task.progress = min(max(progress, 0), 100)
        # TODO: Add message to task status updates 
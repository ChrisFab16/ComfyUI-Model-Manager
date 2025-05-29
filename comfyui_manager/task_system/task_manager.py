"""Task manager implementation."""
import asyncio
import time
from typing import Dict, Any, Optional, List
from .base_task import Task, TaskStatus
from .task_handlers import TaskHandlers
from .task_logger import TaskLogger

class TaskManager:
    """Manages task execution in the system."""
    _instance = None
    
    def __init__(self):
        """Initialize task manager."""
        if TaskManager._instance is not None:
            raise RuntimeError("TaskManager is a singleton. Use get_instance() instead.")
        
        self._tasks: Dict[str, Task] = {}
        self._handlers = TaskHandlers.get_instance()
        self._logger = TaskLogger.get_instance()
        self._setup_handlers()

    @classmethod
    def get_instance(cls) -> 'TaskManager':
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = TaskManager()
        return cls._instance

    def _setup_handlers(self):
        """Register task type handlers."""
        # Register built-in handlers
        self._task_handlers = {
            "download_model": self._handlers.handle_download,
            "scan_models": self._handlers.handle_scan,
            "update_metadata": self._handlers.handle_metadata
        }

    def list_tasks(self) -> List[Task]:
        """Get list of all tasks."""
        return list(self._tasks.values())

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        return self._tasks.get(task_id)

    async def create_task(self, task_type: str, params: Dict[str, Any]) -> Task:
        """Create a new task."""
        import uuid
        task = Task(
            id=str(uuid.uuid4()),
            type=task_type,
            params=params
        )
        self._tasks[task.id] = task
        
        # Log task creation
        self._logger.task_started(task.id, task_type, params)
        
        # Start task execution
        if task_type in self._task_handlers:
            asyncio.create_task(self._execute_task(task))
        else:
            error_msg = f"No handler registered for task type: {task_type}"
            self._logger.task_failed(task.id, error_msg)
            task.status = TaskStatus.ERROR
            task.error = error_msg
        
        return task

    async def _execute_task(self, task: Task):
        """Execute a task using its registered handler."""
        try:
            handler = self._task_handlers.get(task.type)
            if handler:
                # Start execution
                task.status = TaskStatus.RUNNING
                self._logger.task_progress(task.id, task.progress, task.status.value)
                
                # Execute the handler
                result = await handler(task)
                
                # Update task status based on result
                if task.status != TaskStatus.ERROR:  # Only if no error occurred during execution
                    task.status = TaskStatus.COMPLETED
                    self._logger.task_completed(task.id, result)
                
            else:
                error_msg = f"No handler found for task type: {task.type}"
                task.status = TaskStatus.ERROR
                task.error = error_msg
                self._logger.task_failed(task.id, error_msg)
                
        except Exception as e:
            error_msg = str(e)
            task.status = TaskStatus.ERROR
            task.error = error_msg
            self._logger.task_failed(task.id, error_msg)
            raise  # Re-raise to propagate error

    async def cancel_task(self, task_id: str):
        """Cancel a task."""
        task = self.get_task(task_id)
        if task and task.status == TaskStatus.RUNNING:
            task.status = TaskStatus.CANCELLED
            self._logger.task_cancelled(task_id)

    async def delete_task(self, task_id: str):
        """Delete a task."""
        if task_id in self._tasks:
            await self.cancel_task(task_id)
            del self._tasks[task_id]
            self._logger.task_deleted(task_id)

    def get_all_tasks(self) -> List[Task]:
        """Get all tasks in the system."""
        return list(self._tasks.values())

    def list_tasks(self, status: Optional[TaskStatus] = None) -> List[Task]:
        """List all tasks, optionally filtered by status."""
        if status is None:
            return list(self._tasks.values())
        return [task for task in self._tasks.values() if task.status == status]

    async def update_task(self, task_id: str, **updates) -> Optional[Task]:
        """Update a task's attributes."""
        task = self.get_task(task_id)
        if task:
            for key, value in updates.items():
                if hasattr(task, key):
                    setattr(task, key, value)
        return task

    async def pause_task(self, task_id: str):
        """Pause a task."""
        task = self.get_task(task_id)
        if task and task.status == TaskStatus.RUNNING:
            task.status = TaskStatus.PAUSED

    async def resume_task(self, task_id: str):
        """Resume a task."""
        task = self.get_task(task_id)
        if task and task.status == TaskStatus.PAUSED:
            task.status = TaskStatus.RUNNING

    async def delete_task(self, task_id: str):
        """Delete a task."""
        if task_id in self._tasks:
            del self._tasks[task_id] 
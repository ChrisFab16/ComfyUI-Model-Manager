"""Task queue implementation."""

from typing import Dict, List, Optional, Any
import asyncio
from enum import Enum
import time
import uuid

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class Task:
    def __init__(self, task_type: str, params: Dict[str, Any]):
        self.id = str(uuid.uuid4())
        self.type = task_type
        self.params = params
        self.status = TaskStatus.PENDING
        self.progress = 0
        self.error = None
        self.created_at = time.time()
        self.started_at: Optional[float] = None
        self.completed_at: Optional[float] = None
        self.result: Optional[Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "status": self.status.value,
            "progress": self.progress,
            "error": str(self.error) if self.error else None,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "result": self.result
        }

class TaskQueue:
    def __init__(self, max_concurrent: int = 3):
        self.tasks: Dict[str, Task] = {}
        self.queue: asyncio.Queue[Task] = asyncio.Queue()
        self.max_concurrent = max_concurrent
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self._stop = False
        self._worker_task: Optional[asyncio.Task] = None
        self.worker = None  # Will be set by TaskManager

    async def start(self):
        """Start the task queue worker."""
        self._stop = False
        self._worker_task = asyncio.create_task(self._worker())

    async def stop(self):
        """Stop the task queue worker."""
        self._stop = True
        if self._worker_task:
            await self._worker_task

    async def add_task(self, task_type: str, params: Dict[str, Any]) -> Task:
        """Add a new task to the queue."""
        task = Task(task_type, params)
        self.tasks[task.id] = task
        await self.queue.put(task)
        return task

    async def cancel_task(self, task_id: str):
        """Cancel a task by ID."""
        if task_id in self.running_tasks:
            self.running_tasks[task_id].cancel()
            if task_id in self.tasks:
                self.tasks[task_id].status = TaskStatus.CANCELLED

    async def pause_task(self, task_id: str):
        """Pause a running task."""
        if task_id in self.tasks:
            task = self.tasks[task_id]
            if task.status == TaskStatus.RUNNING:
                task.status = TaskStatus.PAUSED

    async def resume_task(self, task_id: str):
        """Resume a paused task."""
        if task_id in self.tasks:
            task = self.tasks[task_id]
            if task.status == TaskStatus.PAUSED:
                task.status = TaskStatus.PENDING
                await self.queue.put(task)

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        return self.tasks.get(task_id)

    def list_tasks(self, status: Optional[TaskStatus] = None) -> List[Task]:
        """List all tasks, optionally filtered by status."""
        tasks = list(self.tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        return sorted(tasks, key=lambda t: t.created_at, reverse=True)

    async def _worker(self):
        """Main worker loop processing tasks from the queue."""
        while not self._stop:
            # Clean up completed tasks
            self.running_tasks = {
                tid: task for tid, task in self.running_tasks.items()
                if not task.done()
            }

            # Process new tasks if we have capacity
            while len(self.running_tasks) < self.max_concurrent:
                try:
                    task = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    break

                if task.status == TaskStatus.PENDING and self.worker:
                    task.status = TaskStatus.RUNNING
                    task.started_at = time.time()
                    runner = asyncio.create_task(self._run_task(task))
                    self.running_tasks[task.id] = runner

            await asyncio.sleep(0.1)

    async def _run_task(self, task: Task):
        """Execute a single task."""
        try:
            if not self.worker:
                raise ValueError("No worker registered to execute tasks")
                
            task.result = await self.worker.execute(task)
            task.status = TaskStatus.COMPLETED
        except asyncio.CancelledError:
            task.status = TaskStatus.CANCELLED
            task.error = "Task cancelled"
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
        finally:
            task.completed_at = time.time() 
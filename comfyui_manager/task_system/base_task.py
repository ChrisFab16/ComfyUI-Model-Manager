"""Base task interface for the task system."""
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from enum import Enum

class TaskStatus(Enum):
    """Task status enum."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"
    MODEL_EXISTS = "model_exists"  # When model file exists and is complete

@dataclass
class Task:
    """Base task class."""
    id: str
    type: str
    params: Dict[str, Any]
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary."""
        return {
            "id": self.id,
            "type": self.type,
            "params": self.params,
            "status": self.status.value,
            "progress": self.progress,
            "error": self.error
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Task':
        """Create task from dictionary."""
        return cls(
            id=data["id"],
            type=data["type"],
            params=data["params"],
            status=TaskStatus(data.get("status", "pending")),
            progress=data.get("progress", 0.0),
            error=data.get("error")
        ) 
from dataclasses import dataclass
from typing import Literal, Union, Optional

@dataclass
class TaskStatus:
    """Represents the status of a task."""
    taskId: str
    type: str
    fullname: str
    preview: str
    status: Literal["pause", "waiting", "doing"] = "pause"
    platform: Union[str, None] = None
    downloadedSize: float = 0
    totalSize: float = 0
    progress: float = 0
    bps: float = 0
    error: Optional[str] = None

    def __init__(self, **kwargs):
        self.taskId = kwargs.get("taskId", None)
        self.type = kwargs.get("type", None)
        self.fullname = kwargs.get("fullname", None)
        self.preview = kwargs.get("preview", None)
        self.status = kwargs.get("status", "pause")
        self.platform = kwargs.get("platform", None)
        self.downloadedSize = kwargs.get("downloadedSize", 0)
        self.totalSize = kwargs.get("totalSize", 0)
        self.progress = kwargs.get("progress", 0)
        self.bps = kwargs.get("bps", 0)
        self.error = kwargs.get("error", None)

    def to_dict(self):
        """Convert task status to dictionary."""
        return {
            "taskId": self.taskId,
            "type": self.type,
            "fullname": self.fullname,
            "preview": self.preview,
            "status": self.status,
            "platform": self.platform,
            "downloadedSize": self.downloadedSize,
            "totalSize": self.totalSize,
            "progress": self.progress,
            "bps": self.bps,
            "error": self.error,
        } 
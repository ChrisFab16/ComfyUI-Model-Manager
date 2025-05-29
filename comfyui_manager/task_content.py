from dataclasses import dataclass
from typing import Optional, Dict

@dataclass
class TaskContent:
    """Represents the content/configuration of a task."""
    type: str
    pathIndex: int
    fullname: str
    description: str
    downloadPlatform: str
    downloadUrl: str
    sizeBytes: float
    taskId: Optional[str] = None
    hashes: Optional[Dict[str, str]] = None

    def __init__(self, **kwargs):
        self.type = kwargs.get("type", None)
        self.pathIndex = int(kwargs.get("pathIndex", 0))
        self.fullname = kwargs.get("fullname", None)
        self.description = kwargs.get("description", None)
        self.downloadPlatform = kwargs.get("downloadPlatform", None)
        self.downloadUrl = kwargs.get("downloadUrl", None)
        self.sizeBytes = float(kwargs.get("sizeBytes", 0))
        self.taskId = kwargs.get("taskId", None)
        self.hashes = kwargs.get("hashes", None)

    def to_dict(self):
        """Convert task content to dictionary."""
        return {
            "type": self.type,
            "pathIndex": self.pathIndex,
            "fullname": self.fullname,
            "description": self.description,
            "downloadPlatform": self.downloadPlatform,
            "downloadUrl": self.downloadUrl,
            "sizeBytes": self.sizeBytes,
            "taskId": self.taskId,
            "hashes": self.hashes,
        } 
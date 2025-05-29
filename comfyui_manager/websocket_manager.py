"""WebSocket manager for ComfyUI Model Manager."""

from typing import Any, Dict, Set
import logging
from aiohttp import web
from server import PromptServer

from . import config


def print_debug(msg: str):
    """Print debug message with plugin tag."""
    logging.debug(f"[{config.extension_tag}] {msg}")


def print_error(msg: str):
    """Print error message with plugin tag."""
    logging.error(f"[{config.extension_tag}] {msg}")


class WebSocketManager:
    """Manages WebSocket connections and message sending."""
    
    _instance = None

    def __init__(self):
        """Initialize the WebSocket manager."""
        self._websocket_clients: Set[web.WebSocketResponse] = set()
        self._server = PromptServer.instance

    @classmethod
    def get_instance(cls) -> 'WebSocketManager':
        """Get the singleton instance of WebSocketManager."""
        if cls._instance is None:
            cls._instance = WebSocketManager()
        return cls._instance

    def register_client(self, websocket: web.WebSocketResponse) -> None:
        """Register a new WebSocket client."""
        self._websocket_clients.add(websocket)
        print_debug(f"WebSocket client registered. Total clients: {len(self._websocket_clients)}")

    def unregister_client(self, websocket: web.WebSocketResponse) -> None:
        """Unregister a WebSocket client."""
        self._websocket_clients.discard(websocket)
        print_debug(f"WebSocket client unregistered. Total clients: {len(self._websocket_clients)}")

    async def broadcast(self, event_type: str, data: Any) -> None:
        """Broadcast a message to all connected clients."""
        message = {"type": f"model_manager/{event_type}", "data": data}
        
        # First try server's WebSocket clients
        if hasattr(self._server, 'websockets'):
            server_websockets = self._server.websockets
            if server_websockets:
                for ws in server_websockets:
                    try:
                        if not ws.closed:
                            await ws.send_json(message)
                            print_debug(f"Sent {event_type} message via server WebSocket")
                    except Exception as e:
                        print_error(f"Failed to send WebSocket message via server: {str(e)}")

        # Then try our registered clients
        if self._websocket_clients:
            for ws in list(self._websocket_clients):
                try:
                    if not ws.closed:
                        await ws.send_json(message)
                        print_debug(f"Sent {event_type} message via client WebSocket")
                    else:
                        self._websocket_clients.discard(ws)
                except Exception as e:
                    print_error(f"Failed to send WebSocket message to client: {str(e)}")
                    self._websocket_clients.discard(ws)

    async def send_to_client(self, websocket: web.WebSocketResponse, event_type: str, data: Any) -> bool:
        """Send a message to a specific client."""
        if websocket.closed:
            self._websocket_clients.discard(websocket)
            return False

        try:
            message = {"type": f"model_manager/{event_type}", "data": data}
            await websocket.send_json(message)
            print_debug(f"Sent {event_type} message to specific client")
            return True
        except Exception as e:
            print_error(f"Failed to send WebSocket message to specific client: {str(e)}")
            self._websocket_clients.discard(websocket)
            return False

    def get_status(self) -> Dict[str, int]:
        """Get the current WebSocket connection status."""
        server_clients = len(self._server.websockets) if hasattr(self._server, 'websockets') else 0
        plugin_clients = len(self._websocket_clients)
        return {
            "server_clients": server_clients,
            "plugin_clients": plugin_clients,
            "total_clients": server_clients + plugin_clients
        } 
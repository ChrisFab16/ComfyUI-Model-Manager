// src/scripts/ComfyAPI.ts
import { DownloadTaskOptions } from 'types/typings';
import { Model } from 'types/typings';

// Re-export ComfyUI globals
export const app = window.comfyAPI.app.app;
export const api = window.comfyAPI.api.api;
export const $el = window.comfyAPI.ui.$el;
export const ComfyApp = window.comfyAPI.app.ComfyApp;
export const ComfyButton = window.comfyAPI.button.ComfyButton;
export const ComfyDialog = window.comfyAPI.dialog.ComfyDialog;

// Interfaces for WebSocket event payloads
interface DownloadTaskEvent {
  taskId: string;
  data: DownloadTaskOptions;
}

interface ScanTaskUpdateEvent {
  task_id: string;
  file: Model;
}

interface ScanTaskCompleteEvent {
  task_id: string;
  results: Model[];
}

interface ScanTaskErrorEvent {
  task_id: string;
  error: string;
}

// WebSocket reconnection and event handling
const initializeApi = () => {
  let ws: WebSocket | null = null;
  let reconnectAttempts = 0;
  const maxReconnectAttempts = 5;
  const reconnectDelay = 3000;

  // Wrap fetchApi to handle FormData and errors
  const originalFetchApi = api.fetchApi;
  api.fetchApi = async (url: string, options: RequestInit = {}): Promise<Response> => {
    const fetchOptions = { ...options };

    // Remove Content-Type for FormData to let browser set boundary
    if (fetchOptions.body instanceof FormData) {
      fetchOptions.headers = {
        ...fetchOptions.headers,
        'Content-Type': undefined,
      };
    }

    try {
      const response = await originalFetchApi(url, fetchOptions);
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || response.statusText);
      }
      return response;
    } catch (error) {
      const errorMessage = error.message || 'Network error';
      console.error('Fetch error:', errorMessage); // Log instead of toast
      throw error;
    }
  };

  // Initialize WebSocket
  const connectWebSocket = () => {
    const wsUrl = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws`;
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('WebSocket connected');
      reconnectAttempts = 0;
      api.dispatchEvent(new CustomEvent('reconnected'));
    };

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        const { type, data } = message;

        switch (type) {
          case 'update_download_task':
            api.dispatchEvent(
              new CustomEvent<DownloadTaskEvent>('update_download_task', {
                detail: { taskId: data.taskId, data },
              }),
            );
            break;
          case 'complete_download_task':
            api.dispatchEvent(
              new CustomEvent<string>('complete_download_task', {
                detail: data.taskId,
              }),
            );
            break;
          case 'update_scan_task':
            api.dispatchEvent(
              new CustomEvent<ScanTaskUpdateEvent>('update_scan_task', {
                detail: { task_id: data.task_id, file: data.file },
              }),
            );
            break;
          case 'complete_scan_task':
            api.dispatchEvent(
              new CustomEvent<ScanTaskCompleteEvent>('complete_scan_task', {
                detail: { task_id: data.task_id, results: data.results },
              }),
            );
            break;
          case 'error_scan_task':
            api.dispatchEvent(
              new CustomEvent<ScanTaskErrorEvent>('error_scan_task', {
                detail: { task_id: data.task_id, error: data.error },
              }),
            );
            break;
          default:
            console.warn('Unknown WebSocket message type:', type);
        }
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };

    ws.onclose = () => {
      console.warn('WebSocket closed');
      if (reconnectAttempts < maxReconnectAttempts) {
        setTimeout(() => {
          reconnectAttempts++;
          console.log(`Reconnecting WebSocket (attempt ${reconnectAttempts}/${maxReconnectAttempts})`);
          connectWebSocket();
        }, reconnectDelay);
      } else {
        console.error('WebSocket connection failed after multiple attempts');
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
  };

  connectWebSocket();

  // Ensure api supports custom events
  if (!api.dispatchEvent || !api.addEventListener) {
    const eventTarget = new EventTarget();
    api.dispatchEvent = (event: Event) => eventTarget.dispatchEvent(event);
    api.addEventListener = (
      type: string,
      listener: EventListenerOrEventListenerObject,
      options?: boolean | AddEventListenerOptions,
    ) => eventTarget.addEventListener(type, listener, options);
  }

  return api;
};

// Initialize enhanced API
initializeApi();

// src/scripts/ComfyAPI.ts
import { DownloadTaskOptions, Model } from 'types/typings'

// Re-export ComfyUI globals
export const app = window.comfyAPI.app.app
export const api = window.comfyAPI.api.api
export const $el = window.comfyAPI.ui.$el
export const ComfyApp = window.comfyAPI.app.ComfyApp
export const ComfyButton = window.comfyAPI.button.ComfyButton
export const ComfyDialog = window.comfyAPI.dialog.ComfyDialog

// Interfaces for WebSocket event payloads
interface DownloadTaskEvent {
  taskId: string
  data: DownloadTaskOptions
}

interface ScanTaskUpdateEvent {
  task_id: string
  file: Model
}

interface ScanTaskCompleteEvent {
  task_id: string
  results: Model[]
}

interface ScanTaskErrorEvent {
  task_id: string
  error: string
}

// WebSocket reconnection and event handling
const initializeApi = () => {
  let ws: WebSocket | null = null
  let reconnectAttempts = 0
  const maxReconnectAttempts = 5
  const reconnectDelay = 3000
  let reconnectTimer: NodeJS.Timeout | null = null

  // Wrap fetchApi to handle FormData, errors, and /model-manager prefix
  const originalFetchApi = api.fetchApi.bind(api)

  api.fetchApi = async (
    url: string,
    options: RequestInit = {},
  ): Promise<Response> => {
    return new Promise(async (resolve, reject) => {
      try {
        const fetchOptions = { ...options }

        // Remove Content-Type for FormData to let browser set boundary
        if (fetchOptions.body instanceof FormData) {
          const headers = { ...fetchOptions.headers }
          delete headers['Content-Type']
          fetchOptions.headers = headers
        }

        // Fix URL routing - avoid double /api prefix
        let finalUrl = url
        if (url.startsWith('/model-manager')) {
          // Model manager endpoints don't need /api prefix
          finalUrl = url
        } else if (!url.startsWith('/api') && !url.startsWith('http')) {
          // Add /api prefix for other endpoints
          finalUrl = `/api${url.startsWith('/') ? url : '/' + url}`
        }

        // Use setTimeout to make this async and non-blocking
        setTimeout(async () => {
          try {
            const response = await originalFetchApi(finalUrl, fetchOptions)

            if (!response.ok) {
              // Handle errors asynchronously
              response
                .json()
                .then((errorData) =>
                  reject(new Error(errorData.error || response.statusText)),
                )
                .catch(() => reject(new Error(response.statusText)))
            } else {
              resolve(response)
            }
          } catch (error) {
            // Log errors without blocking
            console.error('Fetch error:', error.message || 'Network error')
            reject(error)
          }
        }, 0)
      } catch (error) {
        console.error('Fetch setup error:', error)
        reject(error)
      }
    })
  }

  // Initialize WebSocket with non-blocking reconnection
  const connectWebSocket = () => {
    const wsUrl = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws`

    try {
      ws = new WebSocket(wsUrl)

      ws.onopen = () => {
        console.log('WebSocket connected')
        reconnectAttempts = 0
        // Dispatch event asynchronously
        setTimeout(() => {
          api.dispatchEvent(new CustomEvent('reconnected'))
        }, 0)
      }

      ws.onmessage = (event) => {
        // Process messages asynchronously to avoid blocking
        setTimeout(() => {
          try {
            const message = JSON.parse(event.data)
            const { type, data } = message

            // Handle different message types
            switch (type) {
              case 'update_download_task':
                api.dispatchEvent(
                  new CustomEvent<DownloadTaskEvent>('update_download_task', {
                    detail: { taskId: data.taskId, data },
                  }),
                )
                break
              case 'complete_download_task':
                api.dispatchEvent(
                  new CustomEvent<string>('complete_download_task', {
                    detail: data.taskId,
                  }),
                )
                break
              case 'update_scan_task':
                api.dispatchEvent(
                  new CustomEvent<ScanTaskUpdateEvent>('update_scan_task', {
                    detail: { task_id: data.task_id, file: data.file },
                  }),
                )
                break
              case 'complete_scan_task':
                api.dispatchEvent(
                  new CustomEvent<ScanTaskCompleteEvent>('complete_scan_task', {
                    detail: { task_id: data.task_id, results: data.results },
                  }),
                )
                break
              case 'error_scan_task':
                api.dispatchEvent(
                  new CustomEvent<ScanTaskErrorEvent>('error_scan_task', {
                    detail: { task_id: data.task_id, error: data.error },
                  }),
                )
                break
              case 'status':
                // Handle ComfyUI status messages silently
                console.debug('ComfyUI status:', data)
                break
              default:
                console.debug('Unknown WebSocket message type:', type)
            }
          } catch (error) {
            console.error('Error parsing WebSocket message:', error)
          }
        }, 0)
      }

      ws.onclose = (event) => {
        console.warn('WebSocket closed', event.code, event.reason)

        // Clear any existing reconnect timer
        if (reconnectTimer) {
          clearTimeout(reconnectTimer)
        }

        // Only reconnect if it wasn't a clean close and we haven't exceeded attempts
        if (event.code !== 1000 && reconnectAttempts < maxReconnectAttempts) {
          reconnectTimer = setTimeout(() => {
            reconnectAttempts++
            console.log(
              `Reconnecting WebSocket (attempt ${reconnectAttempts}/${maxReconnectAttempts})`,
            )
            connectWebSocket()
          }, reconnectDelay)
        } else if (reconnectAttempts >= maxReconnectAttempts) {
          console.error('WebSocket connection failed after multiple attempts')
        }
      }

      ws.onerror = (error) => {
        console.error('WebSocket error:', error)
        // Don't immediately reconnect on error, let onclose handle it
      }
    } catch (error) {
      console.error('WebSocket connection error:', error)
      // Retry connection after delay if failed to create
      if (reconnectAttempts < maxReconnectAttempts) {
        reconnectTimer = setTimeout(() => {
          reconnectAttempts++
          connectWebSocket()
        }, reconnectDelay)
      }
    }
  }

  // Initialize WebSocket connection
  connectWebSocket()

  // Ensure api supports custom events with non-blocking setup
  if (!api.dispatchEvent || !api.addEventListener) {
    const eventTarget = new EventTarget()

    api.dispatchEvent = (event: Event) => {
      // Make event dispatching async to prevent blocking
      setTimeout(() => {
        try {
          eventTarget.dispatchEvent(event)
        } catch (error) {
          console.error('Error dispatching event:', error)
        }
      }, 0)
      return true
    }

    api.addEventListener = (
      type: string,
      listener: EventListenerOrEventListenerObject,
      options?: boolean | AddEventListenerOptions,
    ) => {
      eventTarget.addEventListener(type, listener, options)
    }

    api.removeEventListener = (
      type: string,
      listener: EventListenerOrEventListenerObject,
      options?: boolean | EventListenerOptions,
    ) => {
      eventTarget.removeEventListener(type, listener, options)
    }
  }

  return api
}

// Initialize enhanced API
initializeApi()

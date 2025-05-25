// src/hooks/store.ts
import { api } from 'scripts/comfyAPI'
import { DownloadTaskOptions, Model } from 'types/typings'
import { inject, InjectionKey, nextTick, provide } from 'vue'

/**
 * Interface for event payloads
 */
interface DownloadUpdatePayload {
  taskId: string
  data: DownloadTaskOptions
}
interface DownloadCompletePayload {
  taskId: string
}
interface ScanUpdatePayload {
  task_id: string
  file: Model
}
interface ScanCompletePayload {
  task_id: string
  results: Model[]
}
type EventPayloads =
  | { 'download:update': DownloadUpdatePayload }
  | { 'download:complete': DownloadCompletePayload }
  | { 'scan:update': ScanUpdatePayload }
  | { 'scan:complete': ScanCompletePayload }

/**
 * Interface for the store provider, defining available stores and event handling.
 */
interface StoreProvider {
  dialog: {
    open: (options: {
      key: string
      title: string
      content: any
      contentProps?: Record<string, any>
    }) => void
    close: (options: { key: string }) => void
  }
  models: {
    update: (model: Model, data: any, formData?: FormData) => Promise<void>
    remove: (model: Model) => Promise<void>
    refresh: () => Promise<void>
  }
  download: {
    refresh: () => Promise<void>
  }
  emit: <K extends keyof EventPayloads>(
    event: K,
    data: EventPayloads[K],
  ) => void
  on: <K extends keyof EventPayloads>(
    event: K,
    callback: (data: EventPayloads[K]) => void,
  ) => void
  off: <K extends keyof EventPayloads>(
    event: K,
    callback: (data: EventPayloads[K]) => void,
  ) => void
  reset: () => void
  dispose?: () => void
}

const providerHooks = new Map<string, () => any>()
let eventListeners: Record<string, ((data: any) => void)[]> = {}
let isDisposed = false

const storeEvent: StoreProvider = {
  dialog: {
    open: () => {},
    close: () => {},
  },
  models: {
    update: async () => {},
    remove: async () => {},
    refresh: async () => {},
  },
  download: {
    refresh: async () => {},
  },
  emit: (event: string, data: any) => {
    if (isDisposed) return

    // Make event emission non-blocking using microtask queue
    Promise.resolve()
      .then(() => {
        if (isDisposed) return

        const callbacks = eventListeners[event]
        if (!callbacks || callbacks.length === 0) return

        // Process callbacks asynchronously to prevent blocking
        callbacks.forEach((callback, index) => {
          // Stagger callback execution to prevent blocking
          setTimeout(() => {
            if (isDisposed) return

            try {
              callback(data)
            } catch (error) {
              console.error(
                `[storeEvent.emit] Error in callback ${index} for event "${event}":`,
                error,
              )
            }
          }, index * 5) // Small delay between callbacks
        })
      })
      .catch((error) => {
        console.error(
          `[storeEvent.emit] Error emitting event "${event}":`,
          error,
        )
      })
  },
  on: (event: string, callback: (data: any) => void) => {
    if (isDisposed) {
      console.warn(
        `[storeEvent.on] Attempted to add listener for "${event}" after disposal`,
      )
      return
    }

    if (!eventListeners[event]) {
      eventListeners[event] = []
    }
    eventListeners[event].push(callback)
  },
  off: (event: string, callback: (data: any) => void) => {
    if (eventListeners[event]) {
      eventListeners[event] = eventListeners[event].filter(
        (cb) => cb !== callback,
      )
      if (eventListeners[event].length === 0) {
        delete eventListeners[event]
      }
    }
  },
  reset: () => {
    eventListeners = {}
    storeEvent.dialog = { open: () => {}, close: () => {} }
    storeEvent.models = {
      update: async () => {},
      remove: async () => {},
      refresh: async () => {},
    }
    storeEvent.download = { refresh: async () => {} }
  },
}

const storeKeys = new Map<string, symbol>()

const getStoreKey = (key: string): symbol => {
  let storeKey = storeKeys.get(key)
  if (!storeKey) {
    storeKey = Symbol(key)
    storeKeys.set(key, storeKey)
  }
  return storeKey
}

/**
 * Initializes all registered stores and returns the store provider.
 * @returns The StoreProvider instance with initialized stores.
 */
export const useStoreProvider = (): StoreProvider => {
  isDisposed = false

  // Initialize stores asynchronously to prevent blocking
  nextTick(() => {
    for (const [key, useHook] of providerHooks) {
      try {
        const result = useHook()
        if (result && !isDisposed) {
          storeEvent[key] = result
        }
      } catch (error) {
        console.error(
          `[useStoreProvider] Failed to initialize store "${key}":`,
          error,
        )
      }
    }
  })

  // Create async, non-blocking WebSocket event handlers
  const handleScanUpdate = (event: CustomEvent<ScanUpdatePayload>) => {
    // Use requestAnimationFrame for smooth UI updates
    requestAnimationFrame(() => {
      if (isDisposed) return
      storeEvent.emit('scan:update', event.detail)
    })
  }

  const handleScanComplete = (event: CustomEvent<ScanCompletePayload>) => {
    requestAnimationFrame(() => {
      if (isDisposed) return
      storeEvent.emit('scan:complete', event.detail)
    })
  }

  const handleDownloadUpdate = (event: CustomEvent<DownloadUpdatePayload>) => {
    requestAnimationFrame(() => {
      if (isDisposed) return
      storeEvent.emit('download:update', event.detail)
    })
  }

  const handleDownloadComplete = (event: CustomEvent<string>) => {
    requestAnimationFrame(() => {
      if (isDisposed) return
      storeEvent.emit('download:complete', { taskId: event.detail })
    })
  }

  // Add error handling wrapper for event listeners
  const safeAddEventListener = (eventType: string, handler: EventListener) => {
    try {
      api.addEventListener(eventType, handler)
    } catch (error) {
      console.error(
        `[useStoreProvider] Failed to add listener for "${eventType}":`,
        error,
      )
    }
  }

  // Register WebSocket event handlers with error handling
  safeAddEventListener('update_scan_task', handleScanUpdate)
  safeAddEventListener('complete_scan_task', handleScanComplete)
  safeAddEventListener('update_download_task', handleDownloadUpdate)
  safeAddEventListener('complete_download_task', handleDownloadComplete)

  // Clean up WebSocket listeners on provider disposal
  const dispose = () => {
    isDisposed = true

    // Use try-catch for each removal to prevent cascading failures
    const safeRemoveEventListener = (
      eventType: string,
      handler: EventListener,
    ) => {
      try {
        api.removeEventListener?.(eventType, handler)
      } catch (error) {
        console.error(
          `[dispose] Failed to remove listener for "${eventType}":`,
          error,
        )
      }
    }

    safeRemoveEventListener('update_scan_task', handleScanUpdate)
    safeRemoveEventListener('complete_scan_task', handleScanComplete)
    safeRemoveEventListener('update_download_task', handleDownloadUpdate)
    safeRemoveEventListener('complete_download_task', handleDownloadComplete)

    // Clear all event listeners
    eventListeners = {}
  }

  return { ...storeEvent, dispose }
}

/**
 * Defines a store with a unique key and initial hook.
 * @param key The unique store identifier.
 * @param useInitial The hook to initialize the store.
 * @returns A function to inject the store instance.
 */
export const defineStore = <T>(
  key: string,
  useInitial: (event: StoreProvider) => T,
): (() => T) => {
  const storeKey = getStoreKey(key) as InjectionKey<T>

  if (providerHooks.has(key)) {
    const errorMessage = `[defineStore] Store key "${key}" already exists.`
    console.error(errorMessage)
    throw new Error(errorMessage)
  }

  providerHooks.set(key, () => {
    try {
      const result = useInitial(storeEvent)

      // Use nextTick to provide the store asynchronously
      nextTick(() => {
        try {
          provide(storeKey, result ?? storeEvent[key])
        } catch (error) {
          console.error(
            `[defineStore] Failed to provide store "${key}":`,
            error,
          )
        }
      })

      return result
    } catch (error) {
      console.error(`[defineStore] Failed to initialize store "${key}":`, error)
      throw error
    }
  })

  const useStore = (): T => {
    const store = inject<T>(storeKey)
    if (!store) {
      const errorMessage = `Store "${key}" not found. Ensure it is provided by a parent component.`
      console.error(errorMessage)
      throw new Error(errorMessage)
    }
    return store
  }

  return useStore
}

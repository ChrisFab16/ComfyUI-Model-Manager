import { inject, InjectionKey, provide, ref, Ref } from 'vue';
import { useToast } from 'hooks/toast';
import { Model, DownloadTaskOptions } from 'types/typings';
import { api } from 'scripts/comfyAPI';

/**
 * Interface for event payloads
 */
interface DownloadUpdatePayload {
  taskId: string;
  data: DownloadTaskOptions;
}
interface DownloadCompletePayload {
  taskId: string;
}
interface ScanUpdatePayload {
  task_id: string;
  file: Model;
}
interface ScanCompletePayload {
  task_id: string;
  results: Model[];
}
type EventPayloads =
  | { 'download:update': DownloadUpdatePayload }
  | { 'download:complete': DownloadCompletePayload }
  | { 'scan:update': ScanUpdatePayload }
  | { 'scan:complete': ScanCompletePayload };

/**
 * Interface for the store provider, defining available stores and event handling.
 */
interface StoreProvider {
  dialog: {
    open: (options: {
      key: string;
      title: string;
      content: any;
      contentProps?: Record<string, any>;
    }) => void;
    close: (options: { key: string }) => void;
  };
  models: {
    update: (model: Model, data: any, formData?: FormData) => Promise<void>;
    remove: (model: Model) => Promise<void>;
    refresh: () => Promise<void>;
  };
  download: {
    refresh: () => Promise<void>;
  };
  emit: <K extends keyof EventPayloads>(event: K, data: EventPayloads[K]) => void;
  on: <K extends keyof EventPayloads>(event: K, callback: (data: EventPayloads[K]) => void) => void;
  off: <K extends keyof EventPayloads>(event: K, callback: (data: EventPayloads[K]) => void) => void;
  reset: () => void;
  dispose?: () => void;
}

const providerHooks = new Map<string, () => any>();
let eventListeners: Record<string, ((data: any) => void)[]> = {};

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
    eventListeners[event]?.forEach((callback) => callback(data));
  },
  on: (event: string, callback: (data: any) => void) => {
    if (!eventListeners[event]) {
      eventListeners[event] = [];
    }
    eventListeners[event].push(callback);
  },
  off: (event: string, callback: (data: any) => void) => {
    if (eventListeners[event]) {
      eventListeners[event] = eventListeners[event].filter((cb) => cb !== callback);
      if (eventListeners[event].length === 0) {
        delete eventListeners[event];
      }
    }
  },
  reset: () => {
    eventListeners = {};
    storeEvent.dialog = { open: () => {}, close: () => {} };
    storeEvent.models = {
      update: async () => {},
      remove: async () => {},
      refresh: async () => {},
    };
    storeEvent.download = { refresh: async () => {} };
  },
};

const storeKeys = new Map<string, symbol>();

const getStoreKey = (key: string): symbol => {
  let storeKey = storeKeys.get(key);
  if (!storeKey) {
    storeKey = Symbol(key);
    storeKeys.set(key, storeKey);
  }
  return storeKey;
};

/**
 * Initializes all registered stores and returns the store provider.
 * @returns The StoreProvider instance with initialized stores.
 */
export const useStoreProvider = (): StoreProvider => {
  const { toast } = useToast();

  for (const [key, useHook] of providerHooks) {
    try {
      storeEvent[key] = useHook();
    } catch (error) {
      console.error(`[useStoreProvider] Failed to initialize store "${key}":`, error);
      toast.add({
        severity: 'error',
        summary: 'Store Error',
        detail: `Failed to initialize store "${key}": ${error.message || 'Unknown error'}`,
        life: 5000,
      });
    }
  }

  // Initialize WebSocket event handlers
  const handleScanUpdate = (event: CustomEvent<ScanUpdatePayload>) => {
    storeEvent.emit('scan:update', event.detail);
  };

  const handleScanComplete = (event: CustomEvent<ScanCompletePayload>) => {
    storeEvent.emit('scan:complete', event.detail);
  };

  const handleDownloadUpdate = (event: CustomEvent<DownloadUpdatePayload>) => {
    storeEvent.emit('download:update', event.detail);
  };

  const handleDownloadComplete = (event: CustomEvent<string>) => {
    storeEvent.emit('download:complete', { taskId: event.detail });
  };

  api.addEventListener('update_scan_task', handleScanUpdate);
  api.addEventListener('complete_scan_task', handleScanComplete);
  api.addEventListener('update_download_task', handleDownloadUpdate);
  api.addEventListener('complete_download_task', handleDownloadComplete);

  // Clean up WebSocket listeners on provider disposal
  const dispose = () => {
    api.removeEventListener('update_scan_task', handleScanUpdate);
    api.removeEventListener('complete_scan_task', handleScanComplete);
    api.removeEventListener('update_download_task', handleDownloadUpdate);
    api.removeEventListener('complete_download_task', handleDownloadComplete);
  };

  return { ...storeEvent, dispose };
};

/**
 * Defines a store with a unique key and initial hook.
 * @param key The unique store identifier.
 * @param useInitial The hook to initialize the store.
 * @returns A function to inject the store instance.
 */
export const defineStore = <T>(key: string, useInitial: (event: StoreProvider) => T): (() => T) => {
  const { toast } = useToast();
  const storeKey = getStoreKey(key) as InjectionKey<T>;

  if (providerHooks.has(key)) {
    const errorMessage = `[defineStore] Store key "${key}" already exists.`;
    console.error(errorMessage);
    toast.add({
      severity: 'error',
      summary: 'Store Error',
      detail: errorMessage,
      life: 5000,
    });
    throw new Error(errorMessage);
  }

  providerHooks.set(key, () => {
    try {
      const result = useInitial(storeEvent);
      provide(storeKey, result ?? storeEvent[key]);
      return result;
    } catch (error) {
      console.error(`[defineStore] Failed to initialize store "${key}":`, error);
      toast.add({
        severity: 'error',
        summary: 'Store Error',
        detail: `Failed to initialize store "${key}": ${error.message || 'Unknown error'}`,
        life: 5000,
      });
      throw error;
    }
  });

  const useStore = (): T => {
    const store = inject<T>(storeKey);
    if (!store) {
      const errorMessage = `Store "${key}" not found. Ensure it is provided by a parent component.`;
      console.error(errorMessage);
      toast.add({
        severity: 'error',
        summary: 'Store Error',
        detail: errorMessage,
        life: 5000,
      });
      throw new Error(errorMessage);
    }
    return store;
  };

  return useStore;
};

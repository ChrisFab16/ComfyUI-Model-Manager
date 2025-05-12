export type ContainerSize = { width: number; height: number }
export type ContainerPosition = { left: number; top: number }

export interface BaseModel {
  id: string
  basename: string
  extension?: string | null
  sizeBytes?: number
  type: string
  subFolder?: string | null
  pathIndex: number
  isFolder: boolean
  preview?: string | null
  previewType?: string | null
  description?: string | null
  metadata?: Record<string, string> | null
  downloadUrl?: string | null // For VersionModel compatibility
  downloadPlatform?: string | null // For VersionModel compatibility
}

export interface Model extends BaseModel {
  createdAt?: string | null
  updatedAt?: string | null
  children?: Model[] | null // Only for isFolder: true
}

export interface VersionModel extends BaseModel {
  shortname?: string | null // Deprecated or optional
  downloadUrl?: string | null
  downloadPlatform?: string | null
  hashes?: Record<string, string> | null
}

export type WithResolved<T> = Omit<T, 'preview'> & {
  preview: string | null
}

export type PassThrough<T = void> = T | object | undefined

export interface SelectOptions {
  label: string
  value: any
  icon?: string
  command: () => void
}

export interface SelectFile extends File {
  objectURL: string
}

export interface SelectEvent {
  files: SelectFile[]
  originalEvent: Event
}

export interface DownloadTaskOptions {
  taskId: string
  type: string
  fullname: string
  preview?: string | null
  status: 'pause' | 'waiting' | 'doing' | 'completed' | 'failed'
  progress: number
  downloadedSize: number
  totalSize: number
  bps: number
  error?: string | null
  createdAt?: string | null
  updatedAt?: string | null
}

export interface DownloadTask
  extends Omit<
    DownloadTaskOptions,
    'downloadedSize' | 'totalSize' | 'bps' | 'error'
  > {
  /** Formatted progress (e.g., "1.2 MB / 10 MB") */
  downloadProgress: string
  /** Formatted speed (e.g., "500 KB/s") */
  downloadSpeed: string
  pauseTask: () => Promise<void>
  resumeTask: () => Promise<void>
  deleteTask: () => Promise<void>
}

export type CustomEventListener<T = any> = (event: CustomEvent<T>) => void

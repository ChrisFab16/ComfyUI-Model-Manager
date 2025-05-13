import { useLoading } from 'hooks/loading'
import { useRequest } from 'hooks/request'
import { defineStore } from 'hooks/store'
import { useToast } from 'hooks/toast'
import { BaseModel, DownloadTask, DownloadTaskOptions, SelectOptions, VersionModel } from 'types/typings'
import { bytesToSize } from 'utils/common'
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

export const useDownload = defineStore('download', (store) => {
  const { toast, confirm, wrapperToastError } = useToast()
  const { t } = useI18n()
  const { request } = useRequest()
  const loading = useLoading()

  const taskList = ref<DownloadTask[]>([])

  const createTaskItem = (item: DownloadTaskOptions): DownloadTask => {
    const { taskId, fullname, downloadedSize = 0, totalSize = 0, bps = 0, preview, error, ...rest } = item

    // Validate inputs
    if (!taskId || !fullname) {
      throw new Error('Task ID and fullname are required')
    }
    if (downloadedSize < 0 || totalSize < 0 || bps < 0) {
      throw new Error('Downloaded size, total size, and BPS must be non-negative')
    }

    const progressPercent = totalSize > 0 ? Math.round((downloadedSize / totalSize) * 100) : 0

    const task: DownloadTask = {
      ...rest,
      taskId,
      fullname,
      preview: preview || '/model-manager/preview/no-preview.png',
      downloadProgress: `${bytesToSize(downloadedSize)} / ${bytesToSize(totalSize)} (${progressPercent}%)`,
      downloadSpeed: `${bytesToSize(bps)}/s`,
      pauseTask() {
        wrapperToastError(async () => {
          const response = await request(`/model-manager/download/${taskId}`, {
            method: 'PUT',
            body: JSON.stringify({ status: 'pause' }),
          })
          if (!response.success) {
            throw new Error(response.error || 'Failed to pause task')
          }
          toast.add({
            severity: 'info',
            summary: 'Paused',
            detail: `Paused download for ${fullname}`,
            life: 2000,
          })
        })()
      },
      resumeTask() {
        wrapperToastError(async () => {
          const response = await request(`/model-manager/download/${taskId}`, {
            method: 'PUT',
            body: JSON.stringify({ status: 'resume' }),
          })
          if (!response.success) {
            throw new Error(response.error || 'Failed to resume task')
          }
          toast.add({
            severity: 'info',
            summary: 'Resumed',
            detail: `Resumed download for ${fullname}`,
            life: 2000,
          })
        })()
      },
      cancelTask() {
        confirm.require({
          message: t('cancelAsk', [t('downloadTask').toLowerCase()]),
          header: 'Confirm',
          icon: 'pi pi-info-circle',
          rejectProps: {
            label: t('no'),
            severity: 'secondary',
            outlined: true,
          },
          acceptProps: {
            label: t('yes'),
            severity: 'danger',
          },
          accept: () => {
            wrapperToastError(async () => {
              const response = await request(`/model-manager/download/${taskId}`, {
                method: 'PUT',
                body: JSON.stringify({ status: 'cancel' }),
              })
              if (!response.success) {
                throw new Error(response.error || 'Failed to cancel task')
              }
              taskList.value = taskList.value.filter((task) => task.taskId !== taskId)
              toast.add({
                severity: 'info',
                summary: 'Cancelled',
                detail: `Cancelled download for ${fullname}`,
                life: 2000,
              })
            })()
          },
          reject: () => {},
        })
      },
      deleteTask() {
        confirm.require({
          message: t('deleteAsk', [t('downloadTask').toLowerCase()]),
          header: 'Danger',
          icon: 'pi pi-info-circle',
          rejectProps: {
            label: t('cancel'),
            severity: 'secondary',
            outlined: true,
          },
          acceptProps: {
            label: t('delete'),
            severity: 'danger',
          },
          accept: () => {
            wrapperToastError(async () => {
              const response = await request(`/model-manager/download/${taskId}`, {
                method: 'DELETE',
              })
              if (!response.success) {
                throw new Error(response.error || 'Failed to delete task')
              }
              taskList.value = taskList.value.filter((task) => task.taskId !== taskId)
              toast.add({
                severity: 'success',
                summary: 'Deleted',
                detail: `Deleted download task for ${fullname}`,
                life: 2000,
              })
            })()
          },
          reject: () => {},
        })
      },
    }

    return task
  }

  const refresh = wrapperToastError(async () => {
    loading.show('downloadTasks')
    try {
      const response = await request('/model-manager/download/task', { method: 'GET' })
      if (!response.success) {
        throw new Error(response.error || 'Failed to fetch tasks')
      }
      taskList.value = response.data.map((item: DownloadTaskOptions) => createTaskItem(item))
      return taskList.value
    } catch (error) {
      toast.add({
        severity: 'error',
        summary: 'Error',
        detail: error.message || 'Failed to fetch download tasks',
        life: 5000,
      })
      throw error
    } finally {
      loading.hide('downloadTasks')
    }
  })

  const init = async () => {
    loading.show('downloadSettings')
    try {
      const response = await request('/model-manager/download/init', { method: 'POST' })
      if (!response.success) {
        throw new Error(response.error || 'Failed to initialize download settings')
      }
      store.config.apiKeyInfo.value = response.data
    } catch (error) {
      toast.add({
        severity: 'error',
        summary: 'Error',
        detail: error.message || 'Failed to initialize download settings',
        life: 5000,
      })
    } finally {
      loading.hide('downloadSettings')
    }
  }

  const handleDownloadUpdate = ({ taskId, ...item }: { taskId: string } & Partial<DownloadTaskOptions>) => {
    const task = taskList.value.find((t) => t.taskId === taskId)
    if (!task) {
      console.warn(`Task ${taskId} not found in taskList`)
      return
    }
    if (item.error) {
      toast.add({
        severity: 'error',
        summary: 'Error',
        detail: item.error,
        life: 5000,
      })
      item.error = undefined
    }
    Object.assign(task, createTaskItem({ taskId, ...task, ...item }))
  }

  const handleDownloadComplete = async ({ taskId }: { taskId: string; model?: BaseModel }) => {
    const task = taskList.value.find((item) => item.taskId === taskId)
    taskList.value = taskList.value.filter((item) => item.taskId !== taskId)
    if (task) {
      toast.add({
        severity: 'success',
        summary: 'Success',
        detail: `${task.fullname} download completed`,
        life: 2000,
      })
      // Always refresh models to ensure UI updates
      await store.models.refresh()
    }
  }

  const handleReconnected = () => {
    refresh()
  }

  onMounted(() => {
    init()
    refresh()
    storeEvent.on('download:update', handleDownloadUpdate)
    storeEvent.on('download:complete', handleDownloadComplete)
    storeEvent.on('reconnected', handleReconnected)
  })

  onUnmounted(() => {
    storeEvent.off('download:update', handleDownloadUpdate)
    storeEvent.off('download:complete', handleDownloadComplete)
    storeEvent.off('reconnected', handleReconnected)
  })

  return { data: taskList, refresh }
})

declare module 'hooks/store' {
  interface StoreProvider {
    download: ReturnType<typeof useDownload>
  }
}

export const useModelSearch = () => {
  const { t } = useI18n()
  const { toast } = useToast()
  const { request } = useRequest()
  const loading = useLoading()
  const data = ref<(SelectOptions & { item: VersionModel })[]>([])
  const current = ref<string | number>()
  const currentModel = ref<VersionModel>()

  const handleSearchByUrl = async (url: string) => {
    if (!url) {
      return Promise.resolve([])
    }

    // Validate URL format
    try {
      new URL(url)
    } catch {
      toast.add({
        severity: 'error',
        summary: 'Validation Error',
        detail: 'Invalid URL format',
        life: 5000,
      })
      return []
    }

    loading.show('modelSearch')
    try {
      const response = await request(`/model-manager/model-info?model-page=${encodeURIComponent(url)}`, {
        method: 'GET',
      })
      if (!response.success) {
        throw new Error(response.error || 'Failed to search models')
      }
      const resData: VersionModel[] = response.data
      data.value = resData.map((item) => ({
        label: item.shortname || item.name || item.id || 'Unknown',
        value: item.id,
        item,
        command() {
          current.value = item.id
        },
      }))
      current.value = data.value[0]?.value
      currentModel.value = data.value[0]?.item

      if (resData.length === 0) {
        toast.add({
          severity: 'warn',
          summary: 'No Model Found',
          detail: `No model found for ${url}`,
          life: 5000,
        })
      }

      return resData
    } catch (error) {
      toast.add({
        severity: 'error',
        summary: 'Error',
        detail: error.message || 'Failed to search models',
        life: 5000,
      })
      return []
    } finally {
      loading.hide('modelSearch')
    }
  }

  watch(current, () => {
    currentModel.value = data.value.find(
      (option) => option.value === current.value,
    )?.item
  })

  return { data, current, currentModel, search: handleSearchByUrl }
}

// src/hooks/download.ts
import { useLoading } from 'hooks/loading'
import { request as requestFn } from 'hooks/request' // Removed useRequest
import { defineStore } from 'hooks/store'
import { api } from 'scripts/comfyAPI'
import {
  DownloadTask,
  DownloadTaskOptions,
  SelectOptions,
  VersionModel,
} from 'types/typings'
import { bytesToSize } from 'utils/common'
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

export const useDownload = defineStore('download', (store) => {
  const { t } = useI18n()
  const loading = useLoading()

  const taskList = ref<DownloadTask[]>([])

  const createTaskItem = (item: DownloadTaskOptions): DownloadTask => {
    const {
      taskId,
      fullname,
      downloadedSize = 0,
      totalSize = 0,
      bps = 0,
      preview,
      error,
      ...rest
    } = item
    if (!taskId || !fullname) {
      throw new Error('Task ID and fullname are required')
    }
    if (downloadedSize < 0 || totalSize < 0 || bps < 0) {
      throw new Error(
        'Downloaded size, total size, and BPS must be non-negative',
      )
    }
    const progressPercent =
      totalSize > 0 ? Math.round((downloadedSize / totalSize) * 100) : 0
    const task: DownloadTask = {
      ...rest,
      taskId,
      fullname,
      preview: preview || '/model-manager/preview/no-preview.png',
      downloadProgress: `${bytesToSize(downloadedSize)} / ${bytesToSize(totalSize)} (${progressPercent}%)`,
      downloadSpeed: `${bytesToSize(bps)}/s`,
      async pauseTask() {
        try {
          console.log('createTaskItem: pauseTask taskId=', taskId)
          const response = await requestFn(`/download/${taskId}`, {
            method: 'PUT',
            body: JSON.stringify({ status: 'pause' }),
          })
          if (!response.success) {
            throw new Error(response.error || 'Failed to pause task')
          }
          console.log('Paused', `Paused download for ${fullname}`)
        } catch (error) {
          console.error(
            'createTaskItem: pauseTask error=',
            error.message || 'Failed to pause task',
          )
        }
      },
      async resumeTask() {
        try {
          console.log('createTaskItem: resumeTask taskId=', taskId)
          const response = await requestFn(`/download/${taskId}`, {
            method: 'PUT',
            body: JSON.stringify({ status: 'resume' }),
          })
          if (!response.success) {
            throw new Error(response.error || 'Failed to resume task')
          }
          console.log('Resumed', `Resumed download for ${fullname}`)
        } catch (error) {
          console.error(
            'createTaskItem: resumeTask error=',
            error.message || 'Failed to resume task',
          )
        }
      },
      async cancelTask() {
        try {
          console.log('createTaskItem: cancelTask taskId=', taskId)
          console.log(t('cancelAsk', [t('downloadTask').toLowerCase()]))
          const response = await requestFn(`/download/${taskId}`, {
            method: 'PUT',
            body: JSON.stringify({ status: 'cancel' }),
          })
          if (!response.success) {
            throw new Error(response.error || 'Failed to cancel task')
          }
          taskList.value = taskList.value.filter(
            (task) => task.taskId !== taskId,
          )
          console.log('Cancelled', `Cancelled download for ${fullname}`)
        } catch (error) {
          console.error(
            'createTaskItem: cancelTask error=',
            error.message || 'Failed to cancel task',
          )
        }
      },
      async deleteTask() {
        try {
          console.log('createTaskItem: deleteTask taskId=', taskId)
          console.log(t('deleteAsk', [t('downloadTask').toLowerCase()]))
          const response = await requestFn(`/download/${taskId}`, {
            method: 'DELETE',
          })
          if (!response.success) {
            throw new Error(response.error || 'Failed to delete task')
          }
          taskList.value = taskList.value.filter(
            (task) => task.taskId !== taskId,
          )
          console.log('Deleted', `Deleted download task for ${fullname}`)
        } catch (error) {
          console.error(
            'createTaskItem: deleteTask error=',
            error.message || 'Failed to delete task',
          )
        }
      },
    }
    return task
  }

  const refresh = async () => {
    console.log('useDownload: refresh called')
    loading.show('downloadTasks')
    try {
      console.log('useDownload: calling request for /download/status')
      const response = await requestFn('/download/status', { method: 'GET' })
      console.log('useDownload: refresh response=', response)
      if (!response.success) {
        throw new Error(response.error || 'Failed to fetch tasks')
      }
      taskList.value = response.data.map((item: DownloadTaskOptions) =>
        createTaskItem(item),
      )
      console.log('useDownload: taskList updated=', taskList.value)
      return taskList.value
    } catch (error) {
      console.error(
        'useDownload: refresh error=',
        error.message || 'Failed to fetch download tasks',
      )
      throw error
    } finally {
      loading.hide('downloadTasks')
    }
  }

  const init = async () => {
    console.log('useDownload: init called')
    loading.show('downloadSettings')
    try {
      console.log('useDownload: initializing download settings')
      store.config.apiKeyInfo.value = {}
    } finally {
      loading.hide('downloadSettings')
    }
  }

  const handleDownloadUpdate = ({
    taskId,
    ...item
  }: { taskId: string } & Partial<DownloadTaskOptions>) => {
    console.log(
      'useDownload: handleDownloadUpdate taskId=',
      taskId,
      'item=',
      item,
    )
    const task = taskList.value.find((t) => t.taskId === taskId)
    if (!task) {
      console.warn(`Task ${taskId} not found in taskList`)
      if (item.fullname) {
        taskList.value.push(
          createTaskItem({ taskId, fullname: item.fullname, ...item }),
        )
      }
      return
    }
    if (item.error) {
      console.error('useDownload: handleDownloadUpdate error=', item.error)
      item.error = undefined
    }
    Object.assign(task, createTaskItem({ taskId, ...task, ...item }))
  }

  const handleDownloadComplete = async ({
    taskId,
  }: {
    taskId: string
    path?: string
  }) => {
    console.log('useDownload: handleDownloadComplete taskId=', taskId)
    const task = taskList.value.find((item) => item.taskId === taskId)
    taskList.value = taskList.value.filter((item) => item.taskId !== taskId)
    if (task) {
      console.log('Success', `${task.fullname} download completed`)
      await store.models.refresh()
    }
  }

  const handleReconnected = () => {
    console.log('useDownload: handleReconnected called')
    refresh()
  }

  const handleDownloadTaskUpdate = (event: CustomEvent) => {
    console.log('useDownload: handleDownloadTaskUpdate event=', event.detail)
    const { task_id, ...data } = event.detail
    handleDownloadUpdate({ taskId: task_id, ...data })
  }

  onMounted(() => {
    console.log('useDownload: onMounted called')
    init()
    refresh()
    store.on('download:update', handleDownloadUpdate)
    store.on('download:complete', handleDownloadComplete)
    store.on('reconnected', handleReconnected)
    api.addEventListener('update_download_task', handleDownloadTaskUpdate)
  })

  onUnmounted(() => {
    console.log('useDownload: onUnmounted called')
    store.off('download:update', handleDownloadUpdate)
    store.off('download:complete', handleDownloadComplete)
    store.off('reconnected', handleReconnected)
    api.removeEventListener('update_download_task', handleDownloadTaskUpdate)
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
  const loading = useLoading()
  const data = ref<(SelectOptions & { item: VersionModel })[]>([])
  const current = ref<string | number>()
  const currentModel = ref<VersionModel>()

  const handleSearchByUrl = async (url: string) => {
    console.log('useModelSearch: handleSearchByUrl url=', url)
    if (!url) {
      console.warn('useModelSearch: URL is empty')
      return Promise.resolve([])
    }
    try {
      new URL(url)
    } catch {
      console.error('useModelSearch: Validation Error', 'Invalid URL format')
      return []
    }
    loading.show('modelSearch')
    try {
      const response = await requestFn(
        `/model-info?model-page=${encodeURIComponent(url)}`,
        {
          method: 'GET',
        },
      )
      console.log('useModelSearch: handleSearchByUrl response=', response)
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
        console.warn(
          'useModelSearch: No Model Found',
          `No model found for ${url}`,
        )
      }
      return resData
    } catch (error) {
      console.error(
        'useModelSearch: handleSearchByUrl error=',
        error.message || 'Failed to search models',
      )
      return []
    } finally {
      loading.hide('modelSearch')
    }
  }

  watch(current, () => {
    console.log('useModelSearch: current changed=', current.value)
    currentModel.value = data.value.find(
      (option) => option.value === current.value,
    )?.item
  })

  return { data, current, currentModel, search: handleSearchByUrl }
}

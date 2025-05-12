import { useLoading } from 'hooks/loading'
import { request } from 'hooks/request'
import { defineStore } from 'hooks/store'
import { useToast } from 'hooks/toast'
import { api } from 'scripts/comfyAPI'
import {
  BaseModel,
  DownloadTask,
  DownloadTaskOptions,
  SelectOptions,
  VersionModel,
} from 'types/typings'
import { bytesToSize } from 'utils/common'
import { onBeforeMount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

export const useDownload = defineStore('download', (store) => {
  const { toast, confirm, wrapperToastError } = useToast()
  const { t } = useI18n()

  const taskList = ref<DownloadTask[]>([])

  const createTaskItem = (item: DownloadTaskOptions): DownloadTask => {
    const { downloadedSize, totalSize, bps, preview, ...rest } = item

    const task: DownloadTask = {
      ...rest,
      preview: preview || '/model-manager/preview/no-preview.png', // Fallback to no-preview
      downloadProgress: `${bytesToSize(downloadedSize)} / ${bytesToSize(totalSize)}`,
      downloadSpeed: `${bytesToSize(bps)}/s`,
      pauseTask() {
        wrapperToastError(async () => {
          const response = await request(`/model-manager/download/${item.taskId}`, {
            method: 'PUT',
            body: JSON.stringify({
              status: 'pause',
            }),
          })
          if (!response.success) {
            throw new Error(response.error || 'Failed to pause task')
          }
        })()
      },
      resumeTask() {
        wrapperToastError(async () => {
          const response = await request(`/model-manager/download/${item.taskId}`, {
            method: 'PUT',
            body: JSON.stringify({
              status: 'resume',
            }),
          })
          if (!response.success) {
            throw new Error(response.error || 'Failed to resume task')
          }
        })()
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
              const response = await request(`/model-manager/download/${item.taskId}`, {
                method: 'DELETE',
              })
              if (!response.success) {
                throw new Error(response.error || 'Failed to delete task')
              }
              taskList.value = taskList.value.filter((task) => task.taskId !== item.taskId)
            })()
          },
          reject: () => {},
        })
      },
    }

    return task
  }

  const refresh = wrapperToastError(async () => {
    const response = await request('/model-manager/download/task', { method: 'GET' })
    if (response.success) {
      taskList.value = response.data.map((item: DownloadTaskOptions) => createTaskItem(item))
      return taskList.value
    }
    throw new Error(response.error || 'Failed to fetch tasks')
  })

  // Initialize download settings (e.g., API keys)
  const init = async () => {
    try {
      const response = await request('/model-manager/download/setting', { method: 'GET' })
      if (response.success) {
        store.config.apiKeyInfo.value = response.data
      }
    } catch (error) {
      console.error('Failed to initialize download settings:', error)
    }
  }

  onBeforeMount(() => {
    init()

    api.addEventListener('reconnected', () => {
      refresh()
    })

    api.addEventListener('update_download_task', (event) => {
      const item = event.detail as DownloadTaskOptions
      for (const task of taskList.value) {
        if (task.taskId === item.taskId) {
          if (item.error) {
            toast.add({
              severity: 'error',
              summary: 'Error',
              detail: item.error,
              life: 15000,
            })
            item.error = undefined
          }
          Object.assign(task, createTaskItem(item))
        }
      }
    })

    api.addEventListener('complete_download_task', (event) => {
      const taskId = event.detail as string
      const task = taskList.value.find((item) => item.taskId === taskId)
      taskList.value = taskList.value.filter((item) => item.taskId !== taskId)
      if (task) {
        toast.add({
          severity: 'success',
          summary: 'Success',
          detail: `${task.fullname} Download completed`,
          life: 2000,
        })
      }
      store.models.refresh()
    })
  })

  onMounted(() => {
    refresh()
  })

  return { data: taskList, refresh }
})

declare module 'hooks/store' {
  interface StoreProvider {
    download: ReturnType<typeof useDownload>
  }
}

export const useModelSearch = () => {
  const loading = useLoading()
  const { toast } = useToast()
  const data = ref<(SelectOptions & { item: VersionModel })[]>([])
  const current = ref<string | number>()
  const currentModel = ref<VersionModel>()

  const handleSearchByUrl = async (url: string) => {
    if (!url) {
      return Promise.resolve([])
    }

    loading.show()
    try {
      const response = await request(`/model-manager/model-info?model-page=${encodeURIComponent(url)}`, {
        method: 'GET',
      })
      if (!response.success) {
        throw new Error(response.error || 'Failed to search models')
      }
      const resData: VersionModel[] = response.data
      data.value = resData.map((item) => ({
        label: item.shortname || item.name || item.id,
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
          life: 3000,
        })
      }

      return resData
    } catch (err) {
      toast.add({
        severity: 'error',
        summary: 'Error',
        detail: err.message || 'Failed to search models',
        life: 15000,
      })
      return []
    } finally {
      loading.hide()
    }
  }

  watch(current, () => {
    currentModel.value = data.value.find(
      (option) => option.value === current.value,
    )?.item
  })

  return { data, current, currentModel, search: handleSearchByUrl }
}

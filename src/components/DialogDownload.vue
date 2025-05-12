<template>
  <div class="flex h-full flex-col gap-4">
    <div ref="container" class="whitespace-nowrap px-4">
      <div :class="['flex gap-4', $sm('justify-end')]">
        <Button
          :class="[$sm('w-auto', 'w-full')]"
          :label="$t('createDownloadTask')"
          @click="openCreateTask"
        ></Button>
      </div>
    </div>

    <ResponseScroll>
      <div class="w-full px-4">
        <ul class="m-0 flex list-none flex-col gap-4 p-0">
          <li
            v-for="item in tasks"
            :key="item.taskId"
            class="rounded-lg border border-gray-500 p-4"
          >
            <div class="flex gap-4 overflow-hidden whitespace-nowrap">
              <div class="h-18 preview-aspect">
                <img :src="item.preview" alt="Preview" />
              </div>

              <div class="flex flex-1 flex-col gap-3 overflow-hidden">
                <div class="flex items-center gap-3 overflow-hidden">
                  <span class="flex-1 overflow-hidden text-ellipsis">
                    {{ item.fullname }}
                  </span>
                  <span v-if="item.error" class="text-red-500 text-sm">
                    {{ item.error }}
                  </span>
                  <span v-show="item.status === 'waiting'" class="h-4">
                    <i class="pi pi-spinner pi-spin"></i>
                  </span>
                  <span
                    v-show="item.status === 'doing'"
                    class="h-4 cursor-pointer"
                    @click="pauseTask(item.taskId)"
                  >
                    <i class="pi pi-pause-circle"></i>
                  </span>
                  <span
                    v-show="item.status === 'pause'"
                    class="h-4 cursor-pointer"
                    @click="resumeTask(item.taskId)"
                  >
                    <i class="pi pi-play-circle"></i>
                  </span>
                  <span class="h-4 cursor-pointer" @click="deleteTask(item.taskId)">
                    <i class="pi pi-trash text-red-400"></i>
                  </span>
                </div>
                <div class="h-2 overflow-hidden rounded bg-gray-200">
                  <div
                    class="h-full bg-blue-500 transition-[width]"
                    :style="{ width: `${item.progress}%` }"
                  ></div>
                </div>
                <div class="flex justify-between">
                  <div>{{ formatProgress(item.downloadedSize, item.totalSize) }}</div>
                  <div v-show="item.status === 'doing'">
                    {{ formatSpeed(item.bps) }}
                  </div>
                </div>
              </div>
            </div>
          </li>
          <li v-if="tasks.length === 0" class="text-center text-gray-500">
            {{ $t('noDownloadTasks') }}
          </li>
        </ul>
      </div>
    </ResponseScroll>
  </div>
</template>

<script setup lang="ts">
import DialogCreateTask from 'components/DialogCreateTask.vue'
import ResponseScroll from 'components/ResponseScroll.vue'
import { useContainerQueries } from 'hooks/container'
import { useDialog } from 'hooks/dialog'
import { request } from 'hooks/request'
import Button from 'primevue/button'
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from 'scripts/comfyAPI'

const { t } = useI18n()
const dialog = useDialog()
const container = ref<HTMLElement | null>(null)
const { $sm } = useContainerQueries(container)

const tasks = ref<any[]>([])
const pollingInterval = ref<NodeJS.Timeout | null>(null)

const openCreateTask = () => {
  dialog.open({
    key: `model-manager-create-task-${Date.now()}`,
    title: t('parseModelUrl'),
    content: DialogCreateTask,
  })
}

const fetchTasks = async () => {
  try {
    const response = await request('/model-manager/download/task', { method: 'GET' })
    if (response.success) {
      tasks.value = response.data.map((task: any) => ({
        ...task,
        pauseTask: () => pauseTask(task.taskId),
        resumeTask: () => resumeTask(task.taskId),
        deleteTask: () => deleteTask(task.taskId),
      }))
    } else {
      console.error('Failed to fetch tasks:', response.error)
    }
  } catch (error) {
    console.error('Error fetching tasks:', error)
  }
}

const pollTaskStatus = async () => {
  for (const task of tasks.value) {
    if (task.status === 'doing' || task.status === 'waiting') {
      try {
        const response = await request(`/model-manager/download/status/${task.taskId}`, {
          method: 'GET',
        })
        if (response.success) {
          const updatedTask = response.data
          tasks.value = tasks.value.map((t) =>
            t.taskId === updatedTask.taskId
              ? { ...updatedTask, pauseTask: t.pauseTask, resumeTask: t.resumeTask, deleteTask: t.deleteTask }
              : t
          )
        }
      } catch (error) {
        console.error(`Error polling task ${task.taskId}:`, error)
      }
    }
  }
}

const pauseTask = async (taskId: string) => {
  try {
    const response = await request(`/model-manager/download/${taskId}`, {
      method: 'PUT',
      body: JSON.stringify({ status: 'pause' }),
    })
    if (response.success) {
      tasks.value = tasks.value.map((task) =>
        task.taskId === taskId ? { ...task, status: 'pause' } : task
      )
    } else {
      console.error('Failed to pause task:', response.error)
    }
  } catch (error) {
    console.error('Error pausing task:', error)
  }
}

const resumeTask = async (taskId: string) => {
  try {
    const response = await request(`/model-manager/download/${taskId}`, {
      method: 'PUT',
      body: JSON.stringify({ status: 'resume' }),
    })
    if (response.success) {
      tasks.value = tasks.value.map((task) =>
        task.taskId === taskId ? { ...task, status: 'doing' } : task
      )
    } else {
      console.error('Failed to resume task:', response.error)
    }
  } catch (error) {
    console.error('Error resuming task:', error)
  }
}

const deleteTask = async (taskId: string) => {
  try {
    const response = await request(`/model-manager/download/${taskId}`, {
      method: 'DELETE',
    })
    if (response.success) {
      tasks.value = tasks.value.filter((task) => task.taskId !== taskId)
    } else {
      console.error('Failed to delete task:', response.error)
    }
  } catch (error) {
    console.error('Error deleting task:', error)
  }
}

const formatProgress = (downloaded: number, total: number) => {
  if (total === 0) return '0 B / 0 B'
  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }
  return `${formatBytes(downloaded)} / ${formatBytes(total)}`
}

const formatSpeed = (bps: number) => {
  if (bps === 0) return '0 B/s'
  const k = 1024
  const sizes = ['B/s', 'KB/s', 'MB/s', 'GB/s']
  const i = Math.floor(Math.log(bps) / Math.log(k))
  return parseFloat((bps / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

onMounted(() => {
  fetchTasks()
  pollingInterval.value = setInterval(pollTaskStatus, 1000)
  api.addEventListener('update_download_task', (event) => {
    const updatedTask = event.detail
    tasks.value = tasks.value.map((task) =>
      task.taskId === updatedTask.taskId
        ? { ...updatedTask, pauseTask: task.pauseTask, resumeTask: task.resumeTask, deleteTask: task.deleteTask }
        : task
    )
  })
  api.addEventListener('complete_download_task', (event) => {
    const taskId = event.detail
    tasks.value = tasks.value.filter((task) => task.taskId !== taskId)
  })
})

onUnmounted(() => {
  if (pollingInterval.value) {
    clearInterval(pollingInterval.value)
    pollingInterval.value = null
  }
})
</script>

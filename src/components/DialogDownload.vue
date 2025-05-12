<template>
  <div class="flex h-full flex-col gap-4">
    <div ref="container" class="whitespace-nowrap px-4">
      <div :class="['flex gap-4', $sm('justify-end')]">
        <Button
          :class="[$sm('w-auto', 'w-full')]"
          :label="$t('createDownloadTask')"
          @click="openCreateTask"
        />
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
                    <i class="pi pi-spinner pi-spin" />
                  </span>
                  <span
                    v-show="item.status === 'doing'"
                    class="h-4 cursor-pointer"
                    @click="item.pauseTask()"
                  >
                    <i class="pi pi-pause-circle" />
                  </span>
                  <span
                    v-show="item.status === 'pause'"
                    class="h-4 cursor-pointer"
                    @click="item.resumeTask()"
                  >
                    <i class="pi pi-play-circle" />
                  </span>
                  <span
                    v-show="item.status === 'doing' || item.status === 'waiting'"
                    class="h-4 cursor-pointer"
                    @click="item.cancelTask()"
                  >
                    <i class="pi pi-times-circle text-orange-400" />
                  </span>
                  <span class="h-4 cursor-pointer" @click="item.deleteTask()">
                    <i class="pi pi-trash text-red-400" />
                  </span>
                </div>
                <div class="h-2 overflow-hidden rounded bg-gray-200">
                  <div
                    class="h-full bg-blue-500 transition-[width]"
                    :style="{ width: `${progressPercent(item)}%` }"
                  />
                </div>
                <div class="flex justify-between">
                  <div>{{ item.downloadProgress }}</div>
                  <div v-show="item.status === 'doing'">
                    {{ item.downloadSpeed }}
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
import { useDownload } from 'hooks/download'
import { DownloadTask } from 'types/typings'
import Button from 'primevue/button'
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const dialog = useDialog()
const { data: tasks, refresh } = useDownload()
const container = ref<HTMLElement | null>(null)
const { $sm } = useContainerQueries(container)

const openCreateTask = () => {
  dialog.open({
    key: 'model-manager-create-task',
    title: t('parseModelUrl'),
    content: DialogCreateTask,
  })
}

const progressPercent = (task: DownloadTask) => {
  if (task.totalSize === 0) return 0
  return Math.round((task.downloadedSize / task.totalSize) * 100)
}
</script>

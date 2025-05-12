<template>
  <div class="flex flex-col gap-4">
    <div v-if="editable" class="flex flex-col gap-4">
      <ResponseSelect
        v-if="!baseInfo.type"
        v-model="type"
        :items="typeOptions"
        :loading="isLoading"
        :placeholder="$t('selectModelType')"
      >
        <template #prefix>
          <span>{{ $t('modelType') }}</span>
        </template>
      </ResponseSelect>

      <div class="flex gap-2 overflow-hidden">
        <div class="flex-1 overflow-hidden rounded bg-gray-500/30">
          <div class="flex h-full items-center justify-end">
            <span class="overflow-hidden text-ellipsis whitespace-nowrap px-2">
              {{ renderedModelFolder }}
            </span>
          </div>
        </div>
        <Button
          icon="pi pi-folder"
          :disabled="!type || isLoading"
          :label="$t('selectFolder')"
          @click="handleSelectFolder"
        ></Button>

        <Dialog
          v-model:visible="folderSelectVisible"
          :header="$t('folder')"
          :auto-z-index="false"
          :pt:mask:style="{ zIndex }"
          :pt:root:style="{ height: '50vh', maxWidth: '50vw' }"
          pt:content:class="flex-1"
        >
          <div class="flex h-full flex-col overflow-hidden">
            <div class="flex-1 overflow-hidden">
              <ResponseScroll>
                <Tree
                  class="h-full"
                  v-model:selection-keys="modelFolder"
                  :value="pathOptions"
                  selectionMode="single"
                  :loading="isLoading"
                  :pt:nodeLabel:class="'text-ellipsis overflow-hidden'"
                ></Tree>
              </ResponseScroll>
            </div>
            <div class="flex justify-end gap-2">
              <Button
                :label="$t('cancel')"
                severity="secondary"
                @click="handleCancelSelectFolder"
              ></Button>
              <Button
                :label="$t('select')"
                :disabled="!modelFolder.value || isLoading"
                @click="handleConfirmSelectFolder"
              ></Button>
            </div>
          </div>
        </Dialog>
      </div>

      <div class="flex gap-2">
        <ResponseInput
          v-model.trim.valid="basename"
          class="-mr-2 text-right"
          update-trigger="blur"
          :validate="validateBasename"
          :placeholder="$t('enterModelName')"
        />
        <ResponseInput
          v-model.trim="extension"
          class="w-32 text-right"
          update-trigger="blur"
          :validate="validateExtension"
          :placeholder="$t('extension')"
        />
      </div>
    </div>

    <table class="w-full table-fixed border-collapse border">
      <colgroup>
        <col class="w-32" />
        <col />
      </colgroup>
      <tbody>
        <tr
          v-for="item in information"
          :key="item.key"
          class="h-8 whitespace-nowrap border-b"
        >
          <td class="border-r bg-gray-300 px-4 dark:bg-gray-800">
            {{ $t(`info.${item.key}`) }}
          </td>
          <td
            class="overflow-hidden text-ellipsis break-all px-4"
            v-tooltip.top="{
              value: item.display,
              disabled: !['pathIndex', 'basename'].includes(item.key),
              autoHide: false,
              showDelay: 800,
              hideDelay: 300,
              pt: { root: { style: { zIndex: tooltipZIndex } } },
            }"
          >
            {{ item.display }}
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
import ResponseInput from 'components/ResponseInput.vue'
import ResponseScroll from 'components/ResponseScroll.vue'
import ResponseSelect from 'components/ResponseSelect.vue'
import { useDialog } from 'hooks/dialog'
import { useModelBaseInfo, useModelFolder, useModels } from 'hooks/model'
import { useStoreProvider } from 'hooks/store'
import { useToast } from 'hooks/toast'
import Button from 'primevue/button'
import { usePrimeVue } from 'primevue/config'
import Dialog from 'primevue/dialog'
import Tree from 'primevue/tree'
import { SelectOptions } from 'types/typings'
import { computed, onUnmounted, ref, watch } from 'vue'

const editable = defineModel<boolean>('editable')

const { toast } = useToast()
const { storeEvent } = useStoreProvider()
const { models } = useModels()

const {
  baseInfo,
  pathIndex,
  subFolder,
  basename,
  extension,
  type,
  modelFolders,
} = useModelBaseInfo()

const isLoading = ref(false)

watch(type, () => {
  subFolder.value = ''
  pathIndex.value = 0
})

const typeOptions = computed<SelectOptions[]>(() => {
  return Object.keys(modelFolders.value).map((curr) => ({
    value: curr,
    label: curr,
    disabled: isLoading.value,
    command: () => {
      if (!isLoading.value) {
        type.value = curr
        pathIndex.value = 0
      }
    },
  }))
})

const information = computed(() => {
  return Object.values(baseInfo.value).filter((row) => {
    if (editable.value) {
      const hiddenKeys = ['basename', 'pathIndex', 'extension']
      return !hiddenKeys.includes(row.key)
    }
    return true
  })
})

const validateBasename = (val: string | undefined): boolean => {
  if (!val) {
    toast.add({
      severity: 'error',
      summary: 'Validation Error',
      detail: 'Model name is required',
      life: 5000,
    })
    return false
  }
  const invalidChars = /[\\/:*?"<>|]/
  if (invalidChars.test(val)) {
    toast.add({
      severity: 'error',
      summary: 'Validation Error',
      detail: 'Model name contains invalid characters: \\ / : * ? " < > |',
      life: 5000,
    })
    return false
  }
  const existingModel = models.value[type.value]?.find(
    (m) => m.basename === val && m.subFolder === subFolder.value && m.extension === extension.value
  )
  if (existingModel) {
    toast.add({
      severity: 'error',
      summary: 'Validation Error',
      detail: 'A model with this name already exists in the selected folder',
      life: 5000,
    })
    return false
  }
  return true
}

const validateExtension = (val: string | undefined): boolean => {
  if (!val) {
    return true // Extension is optional
  }
  const validExtensions = ['.safetensors', '.ckpt', '.pt', '.bin', '.pth']
  if (!validExtensions.includes(val.toLowerCase())) {
    toast.add({
      severity: 'error',
      summary: 'Validation Error',
      detail: 'Invalid extension. Allowed: .safetensors, .ckpt, .pt, .bin, .pth',
      life: 5000,
    })
    return false
  }
  return true
}

const folderSelectVisible = ref(false)

const { stack } = useDialog()
const { config } = usePrimeVue()
const zIndex = computed(() => {
  const baseZIndex = config.zIndex?.modal ?? 1100
  return baseZIndex + stack.value.length * 10 + 10
})

const tooltipZIndex = computed(() => {
  return zIndex.value + 100
})

const handleSelectFolder = () => {
  if (!type.value) {
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'Please select a model type first',
      life: 5000,
    })
    return
  }
  folderSelectVisible.value = true
}

const { pathOptions } = useModelFolder({ type })

const selectedModelFolder = ref<string>()

const modelFolder = computed({
  get: () => {
    const folderPath = baseInfo.value.pathIndex?.display || ''
    const selectedKey = selectedModelFolder.value ?? folderPath
    return selectedKey ? { [selectedKey]: true } : {}
  },
  set: (val) => {
    const folderPath = Object.keys(val)[0]
    selectedModelFolder.value = folderPath
  },
})

const renderedModelFolder = computed(() => {
  const display = baseInfo.value.pathIndex?.display || ''
  return display || $t('noFolderSelected')
})

// WebSocket scan updates
const handleScanUpdate = ({ file }: { task_id: string; file: Model }) => {
  if (file.type === type.value) {
    isLoading.value = true
    setTimeout(() => (isLoading.value = false), 1000) // Debounce UI update
  }
}

const handleScanComplete = ({ results }: { task_id: string; results: Model[] }) => {
  if (results.some((m) => m.type === type.value)) {
    isLoading.value = true
    storeEvent.models.refresh().finally(() => (isLoading.value = false))
  }
}

storeEvent.on('scan:update', handleScanUpdate)
storeEvent.on('scan:complete', handleScanComplete)

onUnmounted(() => {
  storeEvent.off('scan:update', handleScanUpdate)
  storeEvent.off('scan:complete', handleScanComplete)
})

const handleCancelSelectFolder = () => {
  selectedModelFolder.value = undefined
  folderSelectVisible.value = false
}

const handleConfirmSelectFolder = () => {
  const folderPath = Object.keys(modelFolder.value)[0]
  if (!folderPath) {
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'No folder selected',
      life: 5000,
    })
    return
  }

  const folders = modelFolders.value[type.value] || []
  const index = folders.findIndex((item) => folderPath.includes(item))
  if (index < 0) {
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'Selected folder is not valid for this model type',
      life: 5000,
    })
    return
  }

  pathIndex.value = index
  const prefixPath = folders[index]
  const subFolderPath = folderPath.replace(prefixPath, '').replace(/^\/+|\/+$/g, '')
  subFolder.value = subFolderPath || ''

  selectedModelFolder.value = undefined
  folderSelectVisible.value = false
}
</script>

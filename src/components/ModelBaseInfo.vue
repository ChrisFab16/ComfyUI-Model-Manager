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
        />
        <Dialog
          v-model:visible="folderSelectVisible"
          :header="$t('folder')"
          :modal="true"
          :style="{ height: '50vh', maxWidth: '50vw' }"
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
                />
              </ResponseScroll>
            </div>
            <div class="flex justify-end gap-2">
              <Button
                :label="$t('cancel')"
                severity="secondary"
                @click="handleCancelSelectFolder"
              />
              <Button
                :label="$t('select')"
                :disabled="!modelFolder || isLoading"
                @click="handleConfirmSelectFolder"
              />
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
import { useModelBaseInfo, useModelFolder, useModels } from 'hooks/model'
import { useStoreProvider } from 'hooks/store'
import { useToast } from 'hooks/toast'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import Tree from 'primevue/tree'
import { BaseModel, SelectOptions, TreeNode } from 'types/typings'
import { computed, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

const editable = defineModel<boolean>('editable')
const { t } = useI18n()
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

watch(type, (newType) => {
  if (newType) {
    subFolder.value = ''
    pathIndex.value = 0
  }
})

const typeOptions = computed<SelectOptions[]>(() => {
  return Object.keys(modelFolders.value).map((curr) => ({
    value: curr,
    label: curr,
    disabled: isLoading.value,
    command: () => {
      if (!isLoading.value) {
        type.value = curr
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
      summary: t('validationError'),
      detail: t('modelNameRequired'),
      life: 5000,
    })
    return false
  }
  const invalidChars = /[\\/:*?"<>|]/
  if (invalidChars.test(val)) {
    toast.add({
      severity: 'error',
      summary: t('validationError'),
      detail: t('modelNameInvalid'),
      life: 5000,
    })
    return false
  }
  if (type.value && models.value[type.value]) {
    const existingModel = models.value[type.value].find(
      (m) => m.basename === val && m.subFolder === subFolder.value && m.extension === extension.value
    )
    if (existingModel) {
      toast.add({
        severity: 'error',
        summary: t('validationError'),
        detail: t('modelNameExists'),
        life: 5000,
      })
      return false
    }
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
      summary: t('validationError'),
      detail: t('extensionInvalid'),
      life: 5000,
    })
    return false
  }
  return true
}

const validateSubFolder = (val: string | undefined): boolean => {
  if (!val) {
    return true // SubFolder is optional
  }
  const invalidChars = /[\\/:*?"<>|]/
  if (invalidChars.test(val)) {
    toast.add({
      severity: 'error',
      summary: t('validationError'),
      detail: t('subFolderInvalid'),
      life: 5000,
    })
    return false
  }
  return true
}

const folderSelectVisible = ref(false)
const selectedModelFolder = ref<string>()

const { pathOptions } = useModelFolder({ type })

const modelFolder = ref<string | null>(null)

const renderedModelFolder = computed(() => {
  return baseInfo.value.pathIndex?.display || t('noFolderSelected')
})

const handleScanUpdate = ({ file }: { task_id: string; file: BaseModel }) => {
  if (file.type === type.value) {
    isLoading.value = true
  }
}

const handleScanComplete = ({ results }: { task_id: string; results: BaseModel[] }) => {
  if (results.some((m) => m.type === type.value)) {
    isLoading.value = true
    storeEvent.models.refresh().finally(() => {
      isLoading.value = false
    })
  }
}

storeEvent.on('scan:update', handleScanUpdate)
storeEvent.on('scan:complete', handleScanComplete)

onUnmounted(() => {
  storeEvent.off('scan:update', handleScanUpdate)
  storeEvent.off('scan:complete', handleScanComplete)
})

const handleSelectFolder = () => {
  if (!type.value) {
    toast.add({
      severity: 'error',
      summary: t('error'),
      detail: t('selectModelTypeFirst'),
      life: 5000,
    })
    return
  }
  folderSelectVisible.value = true
}

const handleCancelSelectFolder = () => {
  modelFolder.value = null
  folderSelectVisible.value = false
}

const handleConfirmSelectFolder = () => {
  if (!modelFolder.value) {
    toast.add({
      severity: 'error',
      summary: t('error'),
      detail: t('noFolderSelected'),
      life: 5000,
    })
    return
  }

  const folderPath = modelFolder.value
  const folders = modelFolders.value[type.value] || []
  const index = folders.findIndex((item) => folderPath.includes(item))
  if (index < 0) {
    toast.add({
      severity: 'error',
      summary: t('error'),
      detail: t('folderInvalid'),
      life: 5000,
    })
    return
  }

  pathIndex.value = index
  const prefixPath = folders[index]
  const subFolderPath = folderPath.replace(prefixPath, '').replace(/^\/+|\/+$/g, '')
  subFolder.value = subFolderPath || ''
  if (subFolder.value && !validateSubFolder(subFolder.value)) {
    subFolder.value = ''
    pathIndex.value = 0
    modelFolder.value = null
    folderSelectVisible.value = false
    return
  }

  folderSelectVisible.value = false
  modelFolder.value = null
  toast.add({
    severity: 'success',
    summary: t('success'),
    detail: t('folderSelected'),
    life: 2000,
  })
}
</script>

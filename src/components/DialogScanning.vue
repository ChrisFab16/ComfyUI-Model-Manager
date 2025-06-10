<template>
  <div class="h-full px-4">
    <div v-show="batchScanningStep === 0" class="h-full">
      <div class="flex h-full items-center px-8">
        <div class="h-20 w-full opacity-60">
          <ProgressBar mode="indeterminate" style="height: 6px"></ProgressBar>
        </div>
      </div>
    </div>

    <Stepper
      v-show="batchScanningStep === 1"
      v-model:value="stepValue"
      class="flex h-full flex-col"
      linear
    >
      <StepList>
        <Step value="1">{{ $t('selectModelType') }}</Step>
        <Step value="2">{{ $t('selectSubdirectory') }}</Step>
        <Step value="3">{{ $t('scanModelInformation') }}</Step>
      </StepList>
      <StepPanels class="flex-1 overflow-hidden">
        <StepPanel value="1" class="h-full">
          <div class="flex h-full flex-col overflow-hidden">
            <ResponseScroll>
              <div class="flex flex-wrap gap-4">
                <Button
                  v-for="item in typeOptions"
                  :key="item.value"
                  :label="item.label"
                  :disabled="isLoading"
                  @click="item.command"
                ></Button>
              </div>
            </ResponseScroll>
          </div>
        </StepPanel>
        <StepPanel value="2" class="h-full">
          <div class="flex h-full flex-col overflow-hidden">
            <ResponseScroll class="flex-1">
              <Tree
                class="h-full"
                v-model:selection-keys="selectedKey"
                :value="pathOptions"
                selectionMode="single"
                :loading="isLoading"
                :pt:nodeLabel:class="'text-ellipsis overflow-hidden'"
              ></Tree>
            </ResponseScroll>

            <div class="flex justify-between pt-6">
              <Button
                :label="$t('back')"
                severity="secondary"
                icon="pi pi-arrow-left"
                @click="handleBackTypeSelect"
              ></Button>
              <Button
                :label="$t('next')"
                icon="pi pi-arrow-right"
                icon-pos="right"
                :disabled="!enabledScan || isLoading"
                @click="handleConfirmSubdir"
              ></Button>
            </div>
          </div>
        </StepPanel>
        <StepPanel value="3" class="h-full">
          <div class="overflow-hidden break-words py-8">
            <div class="overflow-hidden px-8">
              <div v-show="currentType === allType" class="text-center">
                {{ $t('selectedAllPaths') }}
              </div>
              <div v-show="currentType !== allType" class="text-center">
                <div class="pb-2">
                  {{ $t('selectedSpecialPath') }}
                </div>
                <div class="leading-5 opacity-60">
                  {{ selectedModelFolder || $t('noFolderSelected') }}
                </div>
              </div>
            </div>
          </div>

          <div class="flex items-center justify-center gap-4">
            <Button
              v-for="item in scanActions"
              :key="item.value"
              :label="item.label"
              :icon="item.icon"
              :disabled="isLoading"
              @click="item.command"
            ></Button>
          </div>
        </StepPanel>
      </StepPanels>
    </Stepper>

    <div v-show="batchScanningStep === 2" class="h-full">
      <div class="flex h-full flex-col px-8 py-4">
        <div v-if="scanError" class="text-center text-red-500">
          {{ $t('scanError') }}: {{ scanError }}
        </div>
        <div v-else class="flex-1 overflow-auto">
          <div v-if="scanModelsList.length === 0 && scanStatus !== 'running'" class="text-center">
            <Button
              severity="secondary"
              :label="$t('back')"
              icon="pi pi-arrow-left"
              @click="handleBackTypeSelect"
            ></Button>
            <span class="pl-2">{{ $t('noModelsInCurrentPath') }}</span>
          </div>
          <div v-else>
            <ProgressBar :value="scanProgress">
              {{ scanCompleteCount }} / {{ scanTotalCount }}
            </ProgressBar>
            <div class="mt-4">
              <div v-for="model in scanModelsList" :key="model.id" class="py-2">
                <div>{{ model.basename }} ({{ model.subFolder || 'None' }})</div>
                <div class="text-sm opacity-60">
                  {{ bytesToSize(model.sizeBytes) }} | {{ formatDate(model.createdAt) }}
                </div>
              </div>
            </div>
            <div v-if="scanStatus === 'running'" class="mt-4 flex justify-center">
              <Button
                severity="danger"
                :label="$t('cancelScan')"
                icon="pi pi-times"
                :disabled="isLoading"
                @click="handleCancelScan"
              ></Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import ResponseScroll from 'components/ResponseScroll.vue'
import { configSetting } from 'hooks/config'
import { useModelFolder, useModels } from 'hooks/model'
import { useRequest } from 'hooks/request'
import { useStoreProvider } from 'hooks/store'
import { useToast } from 'hooks/toast'
import Button from 'primevue/button'
import ProgressBar from 'primevue/progressbar'
import Step from 'primevue/step'
import StepList from 'primevue/steplist'
import StepPanel from 'primevue/steppanel'
import StepPanels from 'primevue/steppanels'
import Stepper from 'primevue/stepper'
import Tree from 'primevue/tree'
import { api, app } from 'scripts/comfyAPI'
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useWebSocket } from 'hooks/webSocket'
import { Model } from 'types/typings'
import { bytesToSize, formatDate } from 'utils/common'

const { t } = useI18n()
const { toast } = useToast()
const { storeEvent } = useStoreProvider()
const { request } = useRequest()

const stepValue = ref('1')

const { folders, models } = useModels()

const allType = 'All'
const currentType = ref<string>()
const isLoading = ref(false)

const typeOptions = computed(() => {
  const excludeScanTypes = configSetting.excludeScanTypes
    ? configSetting.excludeScanTypes.split(',').map((type) => type.trim()).filter(Boolean)
    : []
  return [
    { label: allType, value: allType },
    ...Object.keys(folders.value)
      .filter((folder) => !excludeScanTypes.includes(folder))
      .map((type) => ({ label: type, value: type })),
  ].map((item) => ({
    ...item,
    command: () => {
      if (!isLoading.value) {
        currentType.value = item.value
        stepValue.value = currentType.value === allType ? '3' : '2'
      }
    },
  }))
})

const { pathOptions } = useModelFolder({ type: currentType })
const selectedModelFolder = ref<string>()
const selectedKey = computed({
  get: () => {
    const key = selectedModelFolder.value
    return key ? { [key]: true } : {}
  },
  set: (val) => {
    const key = Object.keys(val)[0]
    selectedModelFolder.value = key
  },
})

const enabledScan = computed(() => {
  return currentType.value === allType || !!selectedModelFolder.value
})

const handleBackTypeSelect = () => {
  selectedModelFolder.value = undefined
  currentType.value = undefined
  stepValue.value = '1'
  batchScanningStep.value = 1
}

const handleConfirmSubdir = () => {
  if (!enabledScan.value) {
    toast.add({
      severity: 'error',
      summary: 'Validation Error',
      detail: 'Please select a model type or subdirectory',
      life: 5000,
    })
    return
  }
  stepValue.value = '3'
}

const batchScanningStep = ref(0)
const scanModelsList = ref<Model[]>([])
const scanTotalCount = ref(0)
const scanCompleteCount = ref(0)
const scanProgress = computed(() => {
  if (scanTotalCount.value === 0) return 0
  return (scanCompleteCount.value / scanTotalCount.value) * 100
})
const scanStatus = ref<'not_started' | 'running' | 'completed' | 'failed'>('not_started')
const scanError = ref<string | null>(null)
const taskId = ref<string | null>(null)

const handleScanModelInformation = async (mode: 'full' | 'diff') => {
  if (!currentType.value) {
    toast.add({
      severity: 'error',
      summary: 'Validation Error',
      detail: 'Please select a model type',
      life: 5000,
    })
    return
  }

  batchScanningStep.value = 0
  isLoading.value = true
  scanModelsList.value = []
  scanStatus.value = 'running'
  scanError.value = null
  scanTotalCount.value = 0
  scanCompleteCount.value = 0

  try {
    const folder = currentType.value === allType ? 'checkpoints' : currentType.value
    const subFolder = currentType.value === allType ? '' : selectedModelFolder.value || ''
    const response = await request(`/model-manager/scan/start?folder=${folder}&subFolder=${encodeURIComponent(subFolder)}&mode=${mode}`, {
      method: 'GET',
    })
    if (!response.success) {
      throw new Error(response.error || 'Failed to start scan')
    }
    taskId.value = response.task_id
    batchScanningStep.value = 2
  } catch (error) {
    scanError.value = error.message || 'Failed to start scan'
    scanStatus.value = 'failed'
    batchScanningStep.value = 1
    isLoading.value = false
    toast.add({
      severity: 'error',
      summary: 'Scan Error',
      detail: scanError.value,
      life: 5000,
    })
  }
}

const handleCancelScan = async () => {
  if (!taskId.value) return

  isLoading.value = true
  try {
    const response = await request(`/model-manager/scan/stop/${taskId.value}`, {
      method: 'POST',
    })
    if (!response.success) {
      throw new Error(response.error || 'Failed to stop scan')
    }
    scanStatus.value = 'failed'
    scanError.value = 'Scan cancelled by user'
    batchScanningStep.value = 1
    toast.add({
      severity: 'info',
      summary: 'Scan Cancelled',
      detail: 'Model scan was cancelled',
      life: 5000,
    })
  } catch (error) {
    scanError.value = error.message || 'Failed to stop scan'
    toast.add({
      severity: 'error',
      summary: 'Cancel Error',
      detail: scanError.value,
      life: 5000,
    })
  } finally {
    isLoading.value = false
  }
}

const handleScanUpdate = ({ task_id, file }: { task_id: string; file: Model }) => {
  if (task_id === taskId.value && scanStatus.value === 'running') {
    scanModelsList.value = [...scanModelsList.value, file]
    scanCompleteCount.value += 1
  }
}

const handleScanComplete = async ({ task_id, results, total_count }: { task_id: string; results: Model[]; total_count: number }) => {
  if (task_id === taskId.value) {
    scanModelsList.value = results
    scanTotalCount.value = total_count
    scanCompleteCount.value = results.length
    scanStatus.value = 'completed'
    isLoading.value = true // Keep loading state while refreshing
    
    try {
      // Wait for models to refresh
      await storeEvent.models.refresh(true)
      toast.add({
        severity: 'success',
        summary: 'Scan Complete',
        detail: `Found ${results.length} models`,
        life: 2000,
      })
    } catch (error) {
      console.error('Failed to refresh models after scan:', error)
      toast.add({
        severity: 'error',
        summary: 'Refresh Error',
        detail: 'Failed to refresh models after scan',
        life: 5000,
      })
    } finally {
      isLoading.value = false
    }
  }
}

const handleScanError = ({ task_id, error }: { task_id: string; error: string }) => {
  if (task_id === taskId.value) {
    scanError.value = error
    scanStatus.value = 'failed'
    batchScanningStep.value = 1
    isLoading.value = false
    toast.add({
      severity: 'error',
      summary: 'Scan Error',
      detail: error,
      life: 5000,
    })
  }
}

onMounted(() => {
  batchScanningStep.value = 1
  storeEvent.on('scan:update', handleScanUpdate)
  storeEvent.on('scan:complete', handleScanComplete)
  storeEvent.on('scan:error', handleScanError)
})

onUnmounted(() => {
  storeEvent.off('scan:update', handleScanUpdate)
  storeEvent.off('scan:complete', handleScanComplete)
  storeEvent.off('scan:error', handleScanError)
  taskId.value = null
  scanStatus.value = 'not_started'
})

const scanActions = computed(() => [
  {
    value: 'back',
    label: t('back'),
    icon: 'pi pi-arrow-left',
    command: () => {
      stepValue.value = currentType.value === allType ? '1' : '2'
    },
  },
  {
    value: 'full',
    label: t('scanFullInformation'),
    command: () => handleScanModelInformation('full'),
  },
  {
    value: 'diff',
    label: t('scanMissInformation'),
    command: () => handleScanModelInformation('diff'),
  },
])

const refreshTaskContent = async () => {
  const result = await request('/model-info/scan')
  const listContent = result?.models ?? {}
  scanModelsList.value = Object.values(listContent)
  batchScanningStep.value = Object.keys(listContent).length ? 2 : 1
}

// Watch for model updates during scanning
watch(
  () => models.value[currentType.value],
  (newModels) => {
    if (newModels) {
      scanCompleteCount.value = newModels.length
      // Update progress if we have a total count
      if (scanTotalCount.value > 0) {
        scanProgress.value = Math.round((scanCompleteCount.value / scanTotalCount.value) * 100)
      }
    }
  },
  { deep: true }
)

// Handle WebSocket messages for scanning updates
const ws = useWebSocket()
ws.onMessage((message) => {
  if (message.type === 'scan_complete') {
    const { folder, count } = message
    if (folder === currentType.value) {
      scanTotalCount.value = count
      scanProgress.value = 100
    }
  } else if (message.type === 'scan_error') {
    const { folder } = message
    if (folder === currentType.value) {
      scanProgress.value = -1
    }
  }
})

onMounted(() => {
  refreshTaskContent()

  api.addEventListener('update_scan_information_task', (event) => {
    const content = event.detail
    scanModelsList.value = content.models
  })
})
</script>

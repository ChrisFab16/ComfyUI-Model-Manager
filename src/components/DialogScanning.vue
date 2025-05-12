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
                :disabled="!enabledScan"
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
                  {{ selectedModelFolder }}
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
              @click="item.command.call(item)"
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
              <div v-for="model in scanModelsList" :key="model.basename" class="py-2">
                <div>{{ model.basename }} ({{ model.subFolder }})</div>
                <div class="text-sm opacity-60">
                  {{ model.sizeBytes | formatBytes }} | {{ model.createdAt | formatDate }}
                </div>
              </div>
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
import { request } from 'hooks/request'
import Button from 'primevue/button'
import ProgressBar from 'primevue/progressbar'
import Step from 'primevue/step'
import StepList from 'primevue/steplist'
import StepPanel from 'primevue/steppanel'
import StepPanels from 'primevue/steppanels'
import Stepper from 'primevue/stepper'
import Tree from 'primevue/tree'
import { api, app } from 'scripts/comfyAPI'
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const stepValue = ref('1')
const { folders } = useModels()
const allType = 'All'
const currentType = ref<string>()
const typeOptions = computed(() => {
  const excludeScanTypes = app.ui?.settings.getSettingValue<string>(
    configSetting.excludeScanTypes,
  )
  const customBlackList =
    excludeScanTypes
      ?.split(',')
      .map((type) => type.trim())
      .filter(Boolean) ?? []
  return [
    allType,
    ...Object.keys(folders.value).filter(
      (folder) => !customBlackList.includes(folder),
    ),
  ].map((type) => {
    return {
      label: type,
      value: type,
      command: () => {
        currentType.value = type
        stepValue.value = currentType.value === allType ? '3' : '2'
      },
    }
  })
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
  stepValue.value = '3'
}

const batchScanningStep = ref(0)
const scanModelsList = ref<any[]>([])
const scanTotalCount = computed(() => scanModelsList.value.length)
const scanCompleteCount = computed(() => scanModelsList.value.length)
const scanProgress = computed(() => {
  if (scanTotalCount.value === 0) return 0
  return (scanCompleteCount.value / scanTotalCount.value) * 100
})
const scanStatus = ref<string>('not_started')
const scanError = ref<string | null>(null)
const taskId = ref<string | null>(null)

const handleScanModelInformation = async function () {
  batchScanningStep.value = 0
  const mode = this.value
  const folder = currentType.value === allType ? 'checkpoints' : currentType.value // Adjust based on folder type
  scanModelsList.value = []
  scanStatus.value = 'running'
  scanError.value = null

  try {
    const response = await request(`/model-manager/scan/start?folder=${folder}`, {
      method: 'GET',
    })
    if (!response.success) {
      throw new Error(response.error || 'Failed to start scan')
    }
    taskId.value = response.task_id
    batchScanningStep.value = 2
    pollScanStatus()
  } catch (error) {
    scanError.value = error.message || 'Failed to start scan'
    batchScanningStep.value = 1
    scanStatus.value = 'failed'
  }
}

const pollScanStatus = async () => {
  if (!taskId.value || scanStatus.value !== 'running') return

  try {
    const response = await request(`/model-manager/scan/status/${taskId.value}`, {
      method: 'GET',
    })
    if (!response.success) {
      throw new Error(response.error || 'Failed to get scan status')
    }
    scanStatus.value = response.status
    scanModelsList.value = response.data
    scanError.value = response.error

    if (scanStatus.value === 'running') {
      setTimeout(pollScanStatus, 1000)
    } else if (scanStatus.value === 'failed') {
      batchScanningStep.value = 1
    }
  } catch (error) {
    scanError.value = error.message || 'Failed to get scan status'
    scanStatus.value = 'failed'
    batchScanningStep.value = 1
  }
}

const scanActions = ref([
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
    command: handleScanModelInformation,
  },
  {
    value: 'diff',
    label: t('scanMissInformation'),
    command: handleScanModelInformation,
  },
])

onMounted(() => {
  batchScanningStep.value = 1
  api.addEventListener('update_scan_task', (event) => {
    const content = event.detail
    if (content.task_id === taskId.value) {
      scanModelsList.value = [...scanModelsList.value, content.file]
    }
  })
  api.addEventListener('complete_scan_task', (event) => {
    const content = event.detail
    if (content.task_id === taskId.value) {
      scanModelsList.value = content.results
      scanStatus.value = 'completed'
    }
  })
  api.addEventListener('error_scan_task', (event) => {
    const content = event.detail
    if (content.task_id === taskId.value) {
      scanError.value = content.error
      scanStatus.value = 'failed'
      batchScanningStep.value = 1
    }
  })
})

onUnmounted(() => {
  taskId.value = null
  scanStatus.value = 'not_started'
})

const formatBytes = (bytes: number) => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

const formatDate = (timestamp: number) => {
  return new Date(timestamp).toLocaleString()
}
</script>

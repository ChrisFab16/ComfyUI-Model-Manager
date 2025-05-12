<template>
  <form
    ref="container"
    @submit.prevent="handleSubmit"
    @reset.prevent="handleReset"
  >
    <div class="mx-auto w-full max-w-[50rem]">
      <div
        :class="[
          'relative flex gap-4 overflow-hidden',
          $xl('flex-row', 'flex-col'),
        ]"
      >
        <ModelPreview
          class="shrink-0"
          v-model:editable="editable"
        ></ModelPreview>

        <div class="flex flex-col gap-4 overflow-hidden">
          <div class="flex items-center justify-end gap-4">
            <slot name="action" :metadata="formInstance.metadata.value"></slot>
          </div>

          <ModelBaseInfo v-model:editable="editable"></ModelBaseInfo>
        </div>
      </div>

      <Tabs value="0" class="mt-4">
        <TabList>
          <Tab value="0">Description</Tab>
          <Tab value="1">Metadata</Tab>
        </TabList>
        <TabPanels pt:root:class="p-0 py-4">
          <TabPanel value="0">
            <ModelDescription v-model:editable="editable"></ModelDescription>
          </TabPanel>
          <TabPanel value="1">
            <ModelMetadata></ModelMetadata>
          </TabPanel>
        </TabPanels>
      </Tabs>
    </div>
  </form>
</template>

<script setup lang="ts">
import ModelBaseInfo from 'components/ModelBaseInfo.vue'
import ModelDescription from 'components/ModelDescription.vue'
import ModelMetadata from 'components/ModelMetadata.vue'
import ModelPreview from 'components/ModelPreview.vue'
import { useContainerQueries } from 'hooks/container'
import {
  useModelBaseInfoEditor,
  useModelDescriptionEditor,
  useModelFormData,
  useModelMetadataEditor,
  useModelPreviewEditor,
  useModels,
} from 'hooks/model'
import { useToast } from 'hooks/toast'
import { cloneDeep } from 'lodash'
import Tab from 'primevue/tab'
import TabList from 'primevue/tablist'
import TabPanel from 'primevue/tabpanel'
import TabPanels from 'primevue/tabpanels'
import Tabs from 'primevue/tabs'
import { BaseModel, VersionModel, WithResolved } from 'types/typings'
import { previewUrlToFile } from 'utils/common'
import { computed, ref, toRaw, watch } from 'vue'

interface Props {
  model: BaseModel | VersionModel
  isTaskCreation?: boolean // Flag for DialogCreateTask.vue
}

const props = defineProps<Props>()
const editable = defineModel<boolean>('editable')

const emits = defineEmits<{
  submit: [formData: WithResolved<BaseModel>, formDataObj: FormData]
  reset: []
}>()

const { toast, confirm } = useToast()
const { folders } = useModels()
const formInstance = useModelFormData(() => cloneDeep(toRaw(props.model)))
const isDirty = ref(false)

useModelBaseInfoEditor(formInstance)
useModelPreviewEditor(formInstance)
useModelDescriptionEditor(formInstance)
useModelMetadataEditor(formInstance)

// Track form dirtiness
watch(
  () => formInstance.formData.value,
  () => {
    isDirty.value = true
  },
  { deep: true },
)

// Validate form data
const validateForm = (data: WithResolved<BaseModel>): string[] => {
  const errors: string[] = []

  if (!data.basename) {
    errors.push('Model name is required')
  }
  if (!data.type) {
    errors.push('Model type is required')
  } else if (!(data.type in folders.value)) {
    errors.push(`Invalid model type: ${data.type}`)
  }
  if (data.pathIndex == null || data.pathIndex < 0 || data.pathIndex >= (folders.value[data.type]?.length || 0)) {
    errors.push('Invalid path index')
  }
  if (props.isTaskCreation) {
    if (!(data as VersionModel).downloadUrl) {
      errors.push('Download URL is required for task creation')
    }
    if (!(data as VersionModel).downloadPlatform) {
      errors.push('Download platform is required for task creation')
    }
  }

  return errors
}

// Generate FormData for submission
const createFormData = async (data: WithResolved<BaseModel>): Promise<FormData> => {
  const formData = new FormData()
  formData.append('type', data.type || '')
  formData.append('pathIndex', String(data.pathIndex || 0))
  formData.append('fullname', `${data.subFolder || ''}${data.subFolder ? '/' : ''}${data.basename}${data.extension || ''}`)
  formData.append('description', data.description || '')

  if (props.isTaskCreation) {
    const versionModel = data as VersionModel
    formData.append('downloadUrl', versionModel.downloadUrl || '')
    formData.append('downloadPlatform', versionModel.downloadPlatform || '')
  }

  if (data.preview) {
    try {
      const previewFile = await previewUrlToFile(data.preview, data.basename)
      formData.append('previewFile', previewFile)
    } catch (error) {
      throw new Error('Failed to process preview image')
    }
  } else {
    formData.append('previewFile', '')
  }

  return formData
}

const handleReset = () => {
  if (isDirty.value) {
    confirm.require({
      message: 'Are you sure you want to reset the form? All changes will be lost.',
      header: 'Confirm Reset',
      icon: 'pi pi-info-circle',
      rejectProps: {
        label: 'Cancel',
        severity: 'secondary',
        outlined: true,
      },
      acceptProps: {
        label: 'Reset',
        severity: 'danger',
      },
      accept: () => {
        formInstance.reset()
        isDirty.value = false
        emits('reset')
      },
      reject: () => {},
    })
  } else {
    formInstance.reset()
    isDirty.value = false
    emits('reset')
  }
}

const handleSubmit = async () => {
  const data = formInstance.submit()
  const errors = validateForm(data)

  if (errors.length > 0) {
    errors.forEach((error) => {
      toast.add({
        severity: 'error',
        summary: 'Validation Error',
        detail: error,
        life: 5000,
      })
    })
    return
  }

  try {
    const formData = await createFormData(data)
    emits('submit', data, formData)
    isDirty.value = false
  } catch (error) {
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: error.message || 'Failed to process form data',
      life: 5000,
    })
  }
}

watch(
  () => props.model,
  () => {
    if (isDirty.value) {
      confirm.require({
        message: 'You have unsaved changes. Reset the form to load the new model?',
        header: 'Confirm Reset',
        icon: 'pi pi-info-circle',
        rejectProps: {
          label: 'Cancel',
          severity: 'secondary',
          outlined: true,
        },
        acceptProps: {
          label: 'Reset',
          severity: 'danger',
        },
        accept: () => {
          formInstance.reset()
          isDirty.value = false
        },
        reject: () => {},
      })
    } else {
      formInstance.reset()
    }
  },
  { deep: true },
)

const container = ref<HTMLElement | null>(null)
const { $xl } = useContainerQueries(container)
</script>

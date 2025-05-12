<template>
  <ResponseScroll class="h-full">
    <div class="px-8">
      <ModelContent
        v-model:editable="editable"
        :model="modelContent"
        @submit="handleSave"
        @reset="handleCancel"
      >
        <template #action="{ metadata }">
          <template v-if="editable">
            <Button :label="$t('cancel')" type="reset"></Button>
            <Button :label="$t('save')" type="submit"></Button>
          </template>
          <template v-else>
            <Button
              v-if="metadata?.modelPage"
              icon="pi pi-eye"
              :label="$t('viewPage')"
              @click="openModelPage(metadata.modelPage)"
            ></Button>
            <Button
              icon="pi pi-plus"
              :label="$t('addNode')"
              @click.stop="addModelNode(modelContent)"
            ></Button>
            <Button
              icon="pi pi-copy"
              :label="$t('copyNode')"
              @click.stop="copyModelNode(modelContent)"
            ></Button>
            <Button
              v-if="modelContent.preview"
              icon="pi pi-file-import"
              :label="$t('loadWorkflow')"
              @click.stop="loadPreviewWorkflow(modelContent)"
            ></Button>
            <Button
              icon="pi pi-pen-to-square"
              :label="$t('edit')"
              @click="editable = true"
            ></Button>
            <Button
              severity="danger"
              icon="pi pi-trash"
              :label="$t('delete')"
              @click="handleDelete"
            ></Button>
          </template>
        </template>
      </ModelContent>
    </div>
  </ResponseScroll>
</template>

<script setup lang="ts">
import ModelContent from 'components/ModelContent.vue'
import ResponseScroll from 'components/ResponseScroll.vue'
import { api } from 'scripts/comfyAPI'
import { genModelUrl, useModelNodeAction, useModels } from 'hooks/model'
import { useRequest } from 'hooks/request'
import { useToast } from 'hooks/toast'
import Button from 'primevue/button'
import { BaseModel, Model, VersionModel, WithResolved } from 'types/typings'
import { computed, onUnmounted, ref } from 'vue'

interface Props {
  model: Model
}
const props = defineProps<Props>()

const { toast, confirm } = useToast()
const { remove, update } = useModels()
const { addModelNode, copyModelNode, loadPreviewWorkflow } = useModelNodeAction()

const editable = ref(false)

const modelDetailUrl = genModelUrl(props.model)
const { data: extraInfo, error: requestError } = useRequest<Partial<VersionModel> | null>(
  modelDetailUrl,
  {
    method: 'GET',
    defaultValue: null,
    manual: !modelDetailUrl, // Skip if URL is empty
  }
)

// Display request errors
if (requestError.value) {
  toast.add({
    severity: 'error',
    summary: 'Error',
    detail: `Failed to fetch model details: ${requestError.value}`,
    life: 5000,
  })
}

// Merge model with extra info
const modelContent = computed<Model>(() => {
  const base = { ...props.model }
  if (extraInfo.value) {
    return {
      ...base,
      downloadUrl: extraInfo.value.downloadUrl ?? base.downloadUrl,
      downloadPlatform: extraInfo.value.downloadPlatform ?? base.downloadPlatform,
      shortname: extraInfo.value.shortname ?? null,
      hashes: extraInfo.value.hashes ?? null,
      metadata: {
        ...base.metadata,
        ...extraInfo.value.metadata,
        modelPage: extraInfo.value.metadata?.modelPage ?? base.metadata?.modelPage,
      },
    }
  }
  return base
})

// Handle WebSocket scan updates
const handleScanUpdate = (event: CustomEvent<{ task_id: string; file: Model }>) => {
  const { file } = event.detail
  if (file.id === props.model.id) {
    Object.assign(props.model, file)
  }
}

const handleScanComplete = (event: CustomEvent<{ task_id: string; results: Model[] }>) => {
  const { results } = event.detail
  const updatedModel = results.find((m) => m.id === props.model.id)
  if (updatedModel) {
    Object.assign(props.model, updatedModel)
  }
}

api.addEventListener('update_scan_task', handleScanUpdate)
api.addEventListener('complete_scan_task', handleScanComplete)

onUnmounted(() => {
  api.removeEventListener('update_scan_task', handleScanUpdate)
  api.removeEventListener('complete_scan_task', handleScanComplete)
})

const handleCancel = () => {
  editable.value = false
}

const handleSave = async (data: WithResolved<BaseModel>, formData: FormData) => {
  try {
    await update(modelContent.value, data, formData)
    toast.add({
      severity: 'success',
      summary: 'Success',
      detail: 'Model updated successfully',
      life: 2000,
    })
    editable.value = false
  } catch (error) {
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: error.message || 'Failed to update model',
      life: 5000,
    })
  }
}

const handleDelete = () => {
  confirm.require({
    message: `Are you sure you want to delete "${props.model.basename}"? This action cannot be undone.`,
    header: 'Confirm Deletion',
    icon: 'pi pi-exclamation-triangle',
    rejectProps: {
      label: 'Cancel',
      severity: 'secondary',
      outlined: true,
    },
    acceptProps: {
      label: 'Delete',
      severity: 'danger',
    },
    accept: async () => {
      try {
        await remove(props.model)
        toast.add({
          severity: 'success',
          summary: 'Success',
          detail: 'Model deleted successfully',
          life: 2000,
        })
      } catch (error) {
        toast.add({
          severity: 'error',
          summary: 'Error',
          detail: error.message || 'Failed to delete model',
          life: 5000,
        })
      }
    },
    reject: () => {},
  })
}

const openModelPage = (url: string) => {
  try {
    new URL(url) // Validate URL
    window.open(url, '_blank')
  } catch {
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'Invalid model page URL',
      life: 5000,
    })
  }
}

const wrapNodeAction = async <T>(action: () => T, actionName: string): Promise<T> => {
  try {
    const result = await action()
    toast.add({
      severity: 'success',
      summary: 'Success',
      detail: `${actionName} completed successfully`,
      life: 2000,
    })
    return result
  } catch (error) {
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: error.message || `Failed to ${actionName.toLowerCase()}`,
      life: 5000,
    })
    throw error
  }
}
</script>

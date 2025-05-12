<template>
  <div class="flex h-full flex-col gap-4 px-5">
    <ResponseInput
      v-model="modelUrl"
      :allow-clear="true"
      :placeholder="$t('pleaseInputModelUrl')"
      :disabled="isSearching"
      @keypress.enter="searchModelsByUrl"
    >
      <template #suffix>
        <span
          :class="['pi', isSearching ? 'pi-spinner pi-spin' : 'pi-search', 'text-base opacity-60']"
          @click="searchModelsByUrl"
        ></span>
      </template>
    </ResponseInput>

    <div v-show="data.length > 0">
      <ResponseSelect
        v-model="current"
        :items="data"
        :type="isMobile ? 'drop' : 'button'"
      >
        <template #prefix>
          <span>{{ $t('version') }}:</span>
        </template>
      </ResponseSelect>
    </div>

    <ResponseScroll class="-mx-5 h-full">
      <div class="px-5">
        <KeepAlive>
          <ModelContent
            v-if="currentModel"
            :key="currentModel.id"
            :model="currentModel"
            :editable="true"
            :is-task-creation="true"
            @submit="createDownTask"
          >
            <template #action>
              <Button
                icon="pi pi-download"
                :label="$t('download')"
                type="submit"
                :disabled="!canSubmit"
              ></Button>
            </template>
          </ModelContent>
        </KeepAlive>

        <div v-show="data.length === 0">
          <div class="flex flex-col items-center gap-4 py-8">
            <i class="pi pi-box text-3xl"></i>
            <div>{{ $t('noModelsFound') }}</div>
          </div>
        </div>
      </div>
    </ResponseScroll>
  </div>
</template>

<script setup lang="ts">
import ModelContent from 'components/ModelContent.vue'
import ResponseInput from 'components/ResponseInput.vue'
import ResponseScroll from 'components/ResponseScroll.vue'
import ResponseSelect from 'components/ResponseSelect.vue'
import { useConfig } from 'hooks/config'
import { useDialog } from 'hooks/dialog'
import { useModelSearch } from 'hooks/download'
import { useLoading } from 'hooks/loading'
import { useModels } from 'hooks/model'
import { request } from 'hooks/request'
import { useToast } from 'hooks/toast'
import Button from 'primevue/button'
import { VersionModel, WithResolved } from 'types/typings'
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

const { isMobile } = useConfig()
const { toast } = useToast()
const { t } = useI18n()
const loading = useLoading()
const dialog = useDialog()
const { data: models } = useModels()

const modelUrl = ref<string>()
const isSearching = ref(false)

const { current, currentModel, data, search } = useModelSearch()

const canSubmit = computed(() => {
  return (
    currentModel.value &&
    currentModel.value.type &&
    currentModel.value.pathIndex !== undefined &&
    currentModel.value.basename &&
    currentModel.value.downloadUrl &&
    currentModel.value.downloadPlatform &&
    !models.value[currentModel.value.type]?.find(
      (m) =>
        m.basename === currentModel.value.basename &&
        m.subFolder === currentModel.value.subFolder &&
        m.extension === currentModel.value.extension
    )
  )
})

const searchModelsByUrl = async () => {
  if (!modelUrl.value || isSearching.value) return
  isSearching.value = true
  loading.show('searchModels')
  try {
    await search(modelUrl.value)
  } catch (error) {
    toast.add({
      severity: 'error',
      summary: t('error'),
      detail: error.message || t('searchModelsFailed'),
      life: 5000,
    })
  } finally {
    isSearching.value = false
    loading.hide('searchModels')
  }
}

const createDownTask = async (data: WithResolved<VersionModel>) => {
  if (!canSubmit.value) {
    toast.add({
      severity: 'warn',
      summary: t('validationError'),
      detail: t('requiredFieldsMissing'),
      life: 5000,
    })
    return
  }

  loading.show('createTask')
  try {
    const formData = new FormData()
    formData.append('type', data.type)
    formData.append('pathIndex', String(data.pathIndex))
    formData.append('fullname', data.fullname)
    formData.append('extension', data.extension || '')
    formData.append('downloadPlatform', data.downloadPlatform)
    formData.append('downloadUrl', data.downloadUrl)
    if (data.sizeBytes) {
      formData.append('sizeBytes', String(data.sizeBytes))
    }
    if (data.description) {
      formData.append('description', data.description)
    }
    if (data.hashes) {
      formData.append('hashes', JSON.stringify(data.hashes))
    }
    if (data.preview) {
      const previewFile = await previewUrlToFile(data.preview as string)
      formData.append('previewFile', previewFile)
    }

    const response = await request('/model-manager/download', {
      method: 'POST',
      body: formData,
    })

    if (!response.success) {
      throw new Error(response.error || t('createTaskFailed'))
    }

    dialog.close()
    toast.add({
      severity: 'success',
      summary: t('success'),
      detail: t('taskCreated', { name: data.basename }),
      life: 3000,
    })
  } catch (error) {
    toast.add({
      severity: 'error',
      summary: t('error'),
      detail: error.message || t('createTaskFailed'),
      life: 5000,
    })
  } finally {
    loading.hide('createTask')
  }
}
</script>

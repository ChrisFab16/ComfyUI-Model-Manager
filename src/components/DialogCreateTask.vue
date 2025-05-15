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
const { data: models, download } = useModels()

const modelUrl = ref<string>()
const isSearching = ref(false)

const { current, currentModel, data, search } = useModelSearch()

const canSubmit = computed(() => {
  if (!currentModel.value) return false
  const { type, pathIndex, basename, downloadUrl } = currentModel.value
  const isValid =
    type &&
    pathIndex !== undefined &&
    basename &&
    downloadUrl &&
    !models.value[type]?.find(
      (m) =>
        m.basename === basename &&
        m.subFolder === currentModel.value.subFolder &&
        m.extension === currentModel.value.extension
    )
  console.log('canSubmit:', { type, pathIndex, basename, downloadUrl, isValid })
  return isValid
})

const searchModelsByUrl = async () => {
  if (!modelUrl.value || isSearching.value) return
  isSearching.value = true
  loading.show('searchModels')
  try {
    await search(modelUrl.value)
    console.log('Search completed:', data.value)
  } catch (error) {
    console.error('Search error:', error.message || t('searchModelsFailed'))
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
    console.warn('Validation failed:', {
      type: data.type,
      pathIndex: data.pathIndex,
      fullname: data.fullname,
      url: data.downloadUrl,
    })
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
    console.log('Initiating download with data:', {
      type: data.type,
      pathIndex: data.pathIndex,
      fullname: data.fullname,
      url: data.downloadUrl,
    })
    const response = await download({
      type: data.type,
      pathIndex: data.pathIndex,
      fullname: data.fullname,
      url: data.downloadUrl,
    })
    console.log('Download request sent to /api/model-manager/download:', response)

    dialog.close()
    toast.add({
      severity: 'success',
      summary: t('success'),
      detail: t('taskCreated', { name: data.basename }),
      life: 3000,
    })
  } catch (error) {
    console.error('Download error:', error.message || t('createTaskFailed'))
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
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
          <span>version:</span>
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
import { genModelFullName } from 'hooks/model'
import { request } from 'hooks/request'
import { useToast } from 'hooks/toast'
import Button from 'primevue/button'
import { VersionModel, WithResolved } from 'types/typings'
import { previewUrlToFile } from 'utils/common'
import { computed, ref } from 'vue'

const { isMobile } = useConfig()
const { toast } = useToast()
const loading = useLoading()
const dialog = useDialog()

const modelUrl = ref<string>()
const isSearching = ref(false)

const { current, currentModel, data, search } = useModelSearch()

const canSubmit = computed(() => {
  return (
    currentModel.value &&
    currentModel.value.type &&
    currentModel.value.pathIndex !== undefined &&
    currentModel.value.downloadUrl &&
    currentModel.value.downloadPlatform
  )
})

const searchModelsByUrl = async () => {
  if (!modelUrl.value || isSearching.value) return
  isSearching.value = true
  try {
    await search(modelUrl.value)
  } catch (error) {
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: error.message || 'Failed to search models',
      life: 5000,
    })
  } finally {
    isSearching.value = false
  }
}

const createDownTask = async (data: WithResolved<VersionModel>) => {
  if (!canSubmit.value) {
    toast.add({
      severity: 'warn',
      summary: 'Invalid Input',
      detail: 'Please provide all required fields: type, path index, download URL, and platform',
      life: 5000,
    })
    return
  }

  loading.show()
  const formData = new FormData()

  try {
    // Required fields
    formData.append('type', data.type || '')
    formData.append('pathIndex', String(data.pathIndex || 0))
    formData.append('downloadPlatform', data.downloadPlatform || '')
    formData.append('downloadUrl', data.downloadUrl || '')
    formData.append('sizeBytes', String(data.sizeBytes || 0))

    // Optional fields
    if (data.description) {
      formData.append('description', data.description)
    }
    if (data.hashes) {
      formData.append('hashes', JSON.stringify(data.hashes))
    }

    // Compute fullname
    const fullname = genModelFullName(data as VersionModel)
    if (!fullname) {
      throw new Error('Failed to generate model fullname')
    }
    formData.append('fullname', fullname)

    // Handle preview file
    if (data.preview) {
      const previewFile = await previewUrlToFile(data.preview)
      formData.append('previewFile', previewFile)
    } else {
      formData.append('previewFile', '')
    }

    const response = await request('/model-manager/model', {
      method: 'POST',
      body: formData,
    })

    if (!response.success) {
      throw new Error(response.error || 'Failed to create download task')
    }

    dialog.close()
    toast.add({
      severity: 'success',
      summary: 'Success',
      detail: 'Download task created successfully',
      life: 3000,
    })
  } catch (error) {
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: error.message || 'Failed to create download task',
      life: 5000,
    })
  } finally {
    loading.hide()
  }
}
</script>

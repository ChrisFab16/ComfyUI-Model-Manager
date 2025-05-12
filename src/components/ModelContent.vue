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
        />

        <div class="flex flex-col gap-4 overflow-hidden">
          <div class="flex items-center justify-end gap-4">
            <slot name="action" :metadata="formInstance.metadata.value">
              <Button
                type="reset"
                :label="$t('reset')"
                severity="secondary"
                icon="pi pi-undo"
                :disabled="isLoading || !isDirty"
              />
              <Button
                type="submit"
                :label="$t('save')"
                icon="pi pi-save"
                :disabled="isLoading || !isDirty"
                :loading="isLoading"
              />
            </slot>
          </div>

          <ModelBaseInfo v-model:editable="editable" />
        </div>
      </div>

      <Tabs value="0" class="mt-4">
        <TabList>
          <Tab value="0">{{ $t('description') }}</Tab>
          <Tab value="1">{{ $t('metadata') }}</Tab>
        </TabList>
        <TabPanels pt:root:class="p-0 py-4">
          <TabPanel value="0">
            <ModelDescription v-model:editable="editable" />
          </TabPanel>
          <TabPanel value="1">
            <ModelMetadata />
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
import { useLoading } from 'hooks/loading'
import { cloneDeep } from 'lodash'
import Button from 'primevue/button'
import Tab from 'primevue/tab'
import TabList from 'primevue/tablist'
import TabPanel from 'primevue/tabpanel'
import TabPanels from 'primevue/tabpanels'
import Tabs from 'primevue/tabs'
import { BaseModel, VersionModel, WithResolved } from 'types/typings'
import { previewUrlToFile } from 'utils/common'
import { computed, ref, toRaw, watch } from 'vue'
import { useI18n } from 'vue-i18n'

interface Props {
  model: BaseModel | VersionModel
  isTaskCreation?: boolean
}

const props = defineProps<Props>()
const editable = defineModel<boolean>('editable')
const { t } = useI18n()
const { toast, confirm } = useToast()
const loading = useLoading()
const { folders } = useModels()
const formInstance = useModelFormData(() => cloneDeep(toRaw(props.model)))
const isDirty = ref(false)
const isLoading = ref(false)

useModelBaseInfoEditor(formInstance)
useModelPreviewEditor(formInstance)
useModelDescriptionEditor(formInstance)
useModelMetadataEditor(formInstance)

watch(
  () => formInstance.formData.value,
  () => {
    isDirty.value = true
  },
  { deep: true },
)

const validateForm = (data: WithResolved<BaseModel | VersionModel>): string[] => {
  const errors: string[] = []
  const invalidChars = /[\\/:*?"<>|]/

  if (!data.basename) {
    errors.push(t('modelNameRequired'))
  } else if (invalidChars.test(data.basename)) {
    errors.push(t('modelNameInvalid'))
  }
  if (!data.type) {
    errors.push(t('modelTypeRequired'))
  } else if (!(data.type in folders.value)) {
    errors.push(t('modelTypeInvalid', { type: data.type }))
  }
  if (data.pathIndex == null || data.pathIndex < 0 || !folders.value[data.type]?.[data.pathIndex]) {
    errors.push(t('pathIndexInvalid'))
  }
  if (data.subFolder && invalidChars.test(data.subFolder)) {
    errors.push(t('subFolderInvalid'))
  }
  if (props.isTaskCreation) {
    const versionModel = data as VersionModel
    if (!versionModel.downloadUrl) {
      errors.push(t('downloadUrlRequired'))
    }
    if (!versionModel.downloadPlatform) {
      errors.push(t('downloadPlatformRequired'))
    }
  }

  return errors
}

const createFormData = async (data: WithResolved<BaseModel | VersionModel>): Promise<FormData> => {
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
      throw new Error(t('previewProcessingFailed'))
    }
  } else {
    formData.append('previewFile', '')
  }

  return formData
}

const handleReset = () => {
  if (isDirty.value) {
    confirm.require({
      message: t('confirmResetMessage'),
      header: t('confirmReset'),
      icon: 'pi pi-info-circle',
      rejectProps: {
        label: t('cancel'),
        severity: 'secondary',
        outlined: true,
      },
      acceptProps: {
        label: t('reset'),
        severity: 'danger',
      },
      accept: () => {
        formInstance.reset()
        isDirty.value = false
        toast.add({
          severity: 'info',
          summary: t('reset'),
          detail: t('formReset'),
          life: 2000,
        })
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
  if (isLoading.value) return

  const data = formInstance.submit()
  const errors = validateForm(data)

  if (errors.length > 0) {
    errors.forEach((error) => {
      toast.add({
        severity: 'error',
        summary: t('validationError'),
        detail: error,
        life: 5000,
      })
    })
    return
  }

  isLoading.value = true
  loading.show('formSubmit')
  try {
    const formData = await createFormData(data)
    emits('submit', data, formData)
    isDirty.value = false
    toast.add({
      severity: 'success',
      summary: t('success'),
      detail: props.isTaskCreation ? t('taskCreated') : t('modelUpdated'),
      life: 2000,
    })
  } catch (error) {
    toast.add({
      severity: 'error',
      summary: t('error'),
      detail: error.message || t('formProcessingFailed'),
      life: 5000,
    })
  } finally {
    isLoading.value = false
    loading.hide('formSubmit')
  }
}

watch(
  () => props.model,
  () => {
    if (isDirty.value) {
      confirm.require({
        message: t('unsavedChangesMessage'),
        header: t('confirmReset'),
        icon: 'pi pi-info-circle',
        rejectProps: {
          label: t('cancel'),
          severity: 'secondary',
          outlined: true,
        },
        acceptProps: {
          label: t('reset'),
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

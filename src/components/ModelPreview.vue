<template>
  <div class="flex flex-col gap-4">
    <div>
      <div
        class="relative mx-auto w-full overflow-hidden rounded-lg preview-aspect"
        :style="$sm({ width: `${cardWidth}px` })"
      >
        <div v-if="isLoading" class="absolute inset-0 flex items-center justify-center bg-gray-500/50">
          <ProgressSpinner style="width: 50px; height: 50px" />
        </div>

        <div v-if="previewType === 'video' && preview" class="h-full w-full p-1 hover:p-0">
          <video
            class="h-full w-full object-cover"
            playsinline
            autoplay
            loop
            disablepictureinpicture
            preload="metadata"
          >
            <source :src="preview" />
          </video>
        </div>

        <ResponseImage
          v-else-if="preview"
          :src="preview"
          :error="$t('noPreviewAvailable')"
        ></ResponseImage>

        <div
          v-else
          class="flex h-full w-full items-center justify-center bg-gray-200 dark:bg-gray-700"
        >
          {{ $t('noPreviewAvailable') }}
        </div>

        <Carousel
          v-if="defaultContent.length > 1"
          v-show="currentType === 'default'"
          class="absolute top-0 h-full w-full"
          :value="defaultContent"
          v-model:page="defaultContentPage"
          :circular="true"
          :show-navigators="true"
          :show-indicators="false"
          pt:contentcontainer:class="h-full"
          pt:content:class="h-full"
          pt:itemlist:class="h-full"
          :prev-button-props="{
            class: 'absolute left-4 top-1/2 -translate-y-1/2 z-10',
            rounded: true,
            severity: 'secondary',
          }"
          :next-button-props="{
            class: 'absolute right-4 top-1/2 -translate-y-1/2 z-10',
            rounded: true,
            severity: 'secondary',
          }"
        >
          <template #item="slotProps">
            <ResponseImage
              :src="slotProps.data"
              :error="$t('noPreviewAvailable')"
            ></ResponseImage>
          </template>
        </Carousel>
      </div>
    </div>

    <div v-if="editable" class="flex flex-col gap-4 whitespace-nowrap">
      <div class="h-10"></div>
      <div
        :class="[
          'absolute flex h-10 items-center gap-4',
          $xl('left-0 translate-x-0', 'left-1/2 -translate-x-1/2'),
        ]"
      >
        <Button
          v-for="type in typeOptions"
          :key="type"
          :severity="currentType === type ? undefined : 'secondary'"
          :label="$t(type)"
          :disabled="isLoading"
          @click="currentType = type"
        ></Button>
        <Button
          severity="danger"
          icon="pi pi-trash"
          :label="$t('clearPreview')"
          :disabled="isLoading || (!preview && !networkContent && !defaultContent.length)"
          @click="clearPreview"
        ></Button>
      </div>

      <div v-show="currentType === 'network'">
        <div class="absolute left-0 w-full">
          <ResponseInput
            v-model="networkContent"
            prefix-icon="pi pi-globe"
            :allow-clear="true"
            :placeholder="$t('enterPreviewUrl')"
            :validate="validateNetworkContent"
            update-trigger="blur"
          ></ResponseInput>
        </div>
        <div class="h-10"></div>
      </div>

      <div v-show="currentType === 'local'">
        <ResponseFileUpload
          class="absolute left-0 h-24 w-full"
          :accept="supportedFileTypes"
          :max-file-size="maxFileSize"
          @select="updateLocalContent"
          @error="handleUploadError"
          :disabled="isLoading"
        >
        </ResponseFileUpload>
        <div class="h-24"></div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import ResponseFileUpload from 'components/ResponseFileUpload.vue'
import ResponseImage from 'components/ResponseImage.vue'
import ResponseInput from 'components/ResponseInput.vue'
import { useConfig } from 'hooks/config'
import { useContainerQueries } from 'hooks/container'
import { useModelPreview } from 'hooks/model'
import { useStoreProvider } from 'hooks/store'
import { useToast } from 'hooks/toast'
import Button from 'primevue/button'
import Carousel from 'primevue/carousel'
import ProgressSpinner from 'primevue/progressspinner'
import { SelectEvent } from 'types/typings'
import { computed, onUnmounted, ref } from 'vue'

const editable = defineModel<boolean>('editable')
const { cardWidth } = useConfig()
const { toast } = useToast()
const { storeEvent } = useStoreProvider()

const {
  preview,
  previewType,
  typeOptions,
  currentType,
  defaultContent,
  defaultContentPage,
  networkContent,
  updateLocalContent,
  noPreviewContent,
} = useModelPreview()

const isLoading = ref(false)

const supportedFileTypes = 'image/*,video/mp4'
const maxFileSize = 10 * 1024 * 1024 // 10MB

const validateNetworkContent = (url: string | undefined): boolean => {
  if (!url) {
    return true // Optional
  }
  try {
    const parsed = new URL(url)
    if (parsed.protocol !== 'https:') {
      toast.add({
        severity: 'error',
        summary: 'Validation Error',
        detail: 'Only HTTPS URLs are allowed',
        life: 5000,
      })
      return false
    }
    const validExtensions = /\.(jpg|jpeg|png|gif|mp4)$/i
    if (!validExtensions.test(parsed.pathname)) {
      toast.add({
        severity: 'error',
        summary: 'Validation Error',
        detail: 'URL must point to a valid image (jpg, jpeg, png, gif) or video (mp4)',
        life: 5000,
      })
      return false
    }
    return true
  } catch {
    toast.add({
      severity: 'error',
      summary: 'Validation Error',
      detail: 'Invalid URL format',
      life: 5000,
    })
    return false
  }
}

const handleUploadError = (event: { error: string }) => {
  toast.add({
    severity: 'error',
    summary: 'Upload Error',
    detail: event.error || 'Failed to upload preview file',
    life: 5000,
  })
}

const clearPreview = () => {
  preview.value = null
  previewType.value = 'none'
  networkContent.value = null
  defaultContent.value = []
  defaultContentPage.value = 0
  currentType.value = 'default'
  toast.add({
    severity: 'success',
    summary: 'Success',
    detail: 'Preview cleared successfully',
    life: 2000,
  })
}

// WebSocket scan updates
const handleScanUpdate = ({ file }: { task_id: string; file: Model }) => {
  if (file.id === preview.value?.id) {
    isLoading.value = true
    preview.value = file.preview ?? null
    previewType.value = file.previewType ?? 'none'
    setTimeout(() => (isLoading.value = false), 1000) // Debounce UI update
  }
}

const handleScanComplete = ({ results }: { task_id: string; results: Model[] }) => {
  const updatedModel = results.find((m) => m.id === preview.value?.id)
  if (updatedModel) {
    isLoading.value = true
    preview.value = updatedModel.preview ?? null
    previewType.value = updatedModel.previewType ?? 'none'
    setTimeout(() => (isLoading.value = false), 1000)
  }
}

storeEvent.on('scan:update', handleScanUpdate)
storeEvent.on('scan:complete', handleScanComplete)

onUnmounted(() => {
  storeEvent.off('scan:update', handleScanUpdate)
  storeEvent.off('scan:complete', handleScanComplete)
})

const { $sm, $xl } = useContainerQueries()
</script>

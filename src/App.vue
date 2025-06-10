<template>
  <GlobalToast></GlobalToast>
  <GlobalConfirm></GlobalConfirm>
  <GlobalLoading></GlobalLoading>
  <GlobalDialogStack></GlobalDialogStack>
</template>

<script setup lang="ts">
import DialogDownload from 'components/DialogDownload.vue'
import DialogExplorer from 'components/DialogExplorer.vue'
import DialogManager from 'components/DialogManager.vue'
import DialogScanning from 'components/DialogScanning.vue'
import GlobalDialogStack from 'components/GlobalDialogStack.vue'
import GlobalLoading from 'components/GlobalLoading.vue'
import GlobalToast from 'components/GlobalToast.vue'
import { useStoreProvider } from 'hooks/store'
import { useToast } from 'hooks/toast'
import GlobalConfirm from 'primevue/confirmdialog'
import { $el, app, ComfyButton } from 'scripts/comfyAPI'
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const { dialog, models, config, download } = useStoreProvider()
const { toast } = useToast()

const firstOpenManager = ref(true)

onMounted(() => {
  console.log('App.vue mounted')
  console.log('window.comfyAPI:', !!window.comfyAPI)
  console.log('app.ui:', !!app.ui)
  console.log('app.ui.menuContainer:', !!app.ui?.menuContainer)
  console.log('app.menu.settingsGroup:', !!app.menu?.settingsGroup)

  const refreshModelsAndConfig = async () => {
    await Promise.all([models.refresh(true)])
    toast.add({
      severity: 'success',
      summary: 'Refreshed Models',
      life: 2000,
    })
  }

  const openModelScanning = () => {
    dialog.open({
      key: 'model-information-scanning',
      title: t('batchScanModelInformation'),
      content: DialogScanning,
      modal: true,
      defaultSize: { width: 680, height: 490 },
    })
  }

  const openDownloadDialog = () => {
    dialog.open({
      key: 'model-manager-download-list',
      title: t('downloadList'),
      content: DialogDownload,
      headerButtons: [
        {
          key: 'refresh',
          icon: 'pi pi-refresh',
          command: () => download.refresh(),
        },
      ],
    })
  }

  const openManagerDialog = () => {
    console.log('Opening Model Manager dialog')
    const { cardWidth, gutter, aspect, flat } = config

    // Always refresh on open to ensure we have latest data
    models.refresh(true).then(() => {
      firstOpenManager.value = false
    }).catch(error => {
      console.error('Failed to refresh models:', error)
    })

    dialog.open({
      key: 'model-manager',
      title: t('modelManager'),
      content: flat.value ? DialogManager : DialogExplorer,
      keepAlive: true,
      headerButtons: [
        {
          key: 'scanning',
          icon: 'mdi mdi-folder-search-outline text-lg',
          command: openModelScanning,
        },
        {
          key: 'refresh',
          icon: 'pi pi-refresh',
          command: refreshModelsAndConfig,
        },
        {
          key: 'download',
          icon: 'pi pi-download',
          command: openDownloadDialog,
        },
      ],
      minWidth: cardWidth * 2 + gutter + 42,
      minHeight: (cardWidth / aspect) * 0.5 + 162,
      onShow: () => {
        // If models haven't loaded yet, try refreshing again
        if (Object.keys(models.data).length === 0) {
          console.log('No models loaded, refreshing...')
          models.refresh(false)
        }
      }
    })
  }

  if (app.ui?.menuContainer) {
    app.ui.menuContainer.appendChild(
      $el('button', {
        id: 'comfyui-model-manager-button',
        textContent: t('modelManager'),
        onclick: openManagerDialog,
      }),
    )
    console.log('Added menuContainer button')
  } else {
    console.error('Failed to add menuContainer button: menuContainer not found')
  }

  if (app.menu?.settingsGroup) {
    app.menu.settingsGroup.append(
      new ComfyButton({
        icon: 'folder-search',
        tooltip: t('openModelManager'),
        content: t('modelManager'),
        action: openManagerDialog,
      }),
    )
    console.log('Added settingsGroup button')
  } else {
    console.error('Failed to add settingsGroup button: settingsGroup not found')
  }
})
</script>

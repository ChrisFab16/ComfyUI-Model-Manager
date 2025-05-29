// src/hooks/model.ts
import DialogModelDetail from 'components/DialogModelDetail.vue'
import { useLoading } from 'hooks/loading'
import { useMarkdown } from 'hooks/markdown'
import { useRequest } from 'hooks/request'
import { defineStore } from 'hooks/store'
import { castArray, cloneDeep } from 'lodash'
import { TreeNode } from 'primevue/treenode'
import { app } from 'scripts/comfyAPI'
import {
  BaseModel,
  Model,
  SelectEvent,
  VersionModel,
  WithResolved,
} from 'types/typings'
import { bytesToSize, formatDate, previewUrlToFile } from 'utils/common'
import { ModelGrid } from 'utils/legacy'
import { genModelKey, resolveModelTypeLoader } from 'utils/model'
import {
  computed,
  inject,
  type InjectionKey,
  MaybeRefOrGetter,
  onMounted,
  onUnmounted,
  provide,
  ref,
  type Ref,
  toRaw,
  toValue,
  unref,
  watch,
} from 'vue'
import { useI18n } from 'vue-i18n'
import { configSetting } from './config'
import { useWebSocket } from './websocket'

type ModelFolder = Record<string, string[]>

const modelFolderProvideKey = Symbol('modelFolder') as InjectionKey<
  Ref<ModelFolder>
>

export const genModelFullName = (model: BaseModel) => {
  const filename = `${model.basename}${model.extension || ''}`
  return [model.subFolder, filename].filter(Boolean).join('/')
}

export const genModelUrl = (model: BaseModel) => {
  if (!model?.type || model.pathIndex == null || !model.fullname) return ''
  return `/model-manager/model/${model.type}/${model.pathIndex}/${model.fullname}`
}

export const useModels = defineStore('models', (store) => {
  const { t } = useI18n()
  const { request } = useRequest()
  const loading = useLoading()
  const ws = useWebSocket()

  const folders = ref<ModelFolder>({})
  const initialized = ref(false)
  const scanning = ref<Record<string, boolean>>({})
  const models = ref<Record<string, Model[]>>({})

  // Handle WebSocket messages for scanning updates
  ws.onMessage((message) => {
    if (message.type === 'model_found') {
      const { folder, model } = message
      if (!models.value[folder]) {
        models.value[folder] = []
      }
      models.value[folder].push(model)
      models.value[folder].sort((a, b) => {
        if (a.subFolder === b.subFolder) {
          return a.filename.localeCompare(b.filename)
        }
        return a.subFolder.localeCompare(b.subFolder)
      })
    } else if (message.type === 'scan_complete') {
      const { folder } = message
      scanning.value[folder] = false
    } else if (message.type === 'scan_error') {
      const { folder, error } = message
      scanning.value[folder] = false
      toast.add({
        severity: 'error',
        summary: 'Error',
        detail: `Failed to scan ${folder}: ${error}`,
        life: 15000,
      })
    }
  })

  const refreshModels = async (folder: string) => {
    loading.show(folder)
    return request(`/models/${folder}`)
      .then((resData) => {
        const { data, is_scanning } = resData
        models.value[folder] = data
        scanning.value[folder] = is_scanning
        return data
      })
      .finally(() => {
        loading.hide(folder)
      })
  }

  const refreshFolders = async () => {
    loading.show('folders')
    try {
      const response = await request('/models')
      if (!response.success) {
        throw new Error(response.error || t('fetchFoldersFailed'))
      }
      folders.value = response.data || {}
      if (Object.keys(folders.value).length === 0) {
        console.warn(t('warning'), t('noModelFoldersConfigured'))
      }
      initialized.value = true
      console.log('Folders refreshed:', folders.value)
    } catch (error) {
      console.error(t('error'), error.message || t('fetchFoldersFailed'))
    } finally {
      loading.hide('folders')
    }
  }

  provide(modelFolderProvideKey, folders)

  const refreshAllModels = async (force = false) => {
    const forceRefresh = force ? refreshFolders() : Promise.resolve()
    models.value = {}
    scanning.value = {}
    const excludeScanTypes = app.ui?.settings.getSettingValue<string>(
      configSetting.excludeScanTypes,
    )
    const customBlackList =
      excludeScanTypes
        ?.split(',')
        .map((type) => type.trim())
        .filter(Boolean) ?? []
    const results = await forceRefresh.then(() =>
      Promise.allSettled(
        Object.keys(folders.value)
          .filter((folder) => !customBlackList.includes(folder))
          .map(async (folder) => {
            await refreshModels(folder)
          }),
      ),
    )
    const failures = results.filter((r) => r.status === 'rejected').length
    if (failures > 0) {
      console.error(
        t('partialFailure'),
        t('refreshFailures', { count: failures }),
      )
    }
  }

  const downloadModel = async (data: {
    type: string
    pathIndex: number
    fullname: string
    url?: string
  }) => {
    // Validate inputs
    if (!data.type || !(data.type in folders.value)) {
      throw new Error(t('modelTypeInvalid'))
    }
    if (!data.fullname) {
      throw new Error(t('modelNameRequired'))
    }
    if (data.pathIndex < 0 || data.pathIndex >= (folders.value[data.type]?.length || 0)) {
      throw new Error(t('pathIndexInvalid'))
    }

    const formData = new FormData()
    formData.set('type', data.type)
    formData.set('pathIndex', String(data.pathIndex))
    formData.set('fullname', data.fullname)
    if (data.url) {
      formData.set('url', data.url)
    }

    loading.show('downloadModel')
    try {
      console.log('Downloading model:', data)
      const response = await request('/download', {
        method: 'POST',
        body: formData,
        modelManagerPrefix: true,
      })
      if (!response.success) {
        throw new Error(response.error || t('downloadModelFailed'))
      }
      console.log(t('success'), t('downloadStarted', { name: data.fullname }))
      return response
    } catch (error) {
      console.error(t('error'), error.message || t('downloadModelFailed'))
      throw error
    } finally {
      loading.hide('downloadModel')
    }
  }

  const updateModel = async (
    model: BaseModel,
    data: WithResolved<BaseModel | VersionModel>,
    formData?: FormData,
  ) => {
    const updateData = formData || new FormData()
    let oldKey: string | null = null
    let needUpdate = false

    // Validate inputs
    const invalidChars = /[\\/:*?"<>|]/
    if (!data.type || !(data.type in folders.value)) {
      console.error(t('validationError'), t('modelTypeInvalid'))
      return
    }
    if (!data.basename) {
      console.error(t('validationError'), t('modelNameRequired'))
      return
    }
    if (invalidChars.test(data.basename)) {
      console.error(t('validationError'), t('modelNameInvalid'))
      return
    }
    if (data.subFolder && invalidChars.test(data.subFolder)) {
      console.error(t('validationError'), t('subFolderInvalid'))
      return
    }
    if (
      data.extension &&
      !['.safetensors', '.ckpt', '.pt', '.bin', '.pth'].includes(
        data.extension.toLowerCase(),
      )
    ) {
      console.error(t('validationError'), t('extensionInvalid'))
      return
    }
    if (
      data.pathIndex < 0 ||
      data.pathIndex >= (folders.value[data.type]?.length || 0)
    ) {
      console.error(t('validationError'), t('pathIndexInvalid'))
      return
    }
    if (
      models.value[data.type]?.find(
        (m) =>
          m.basename === data.basename &&
          m.subFolder === data.subFolder &&
          m.extension === data.extension,
      )
    ) {
      console.error(t('validationError'), t('modelNameExists'))
      return
    }

    // Check preview
    if (model.preview !== data.preview) {
      if (data.preview) {
        const previewFile = await previewUrlToFile(data.preview as string)
        updateData.set('previewFile', previewFile)
      } else {
        updateData.set('previewFile', '')
      }
      needUpdate = true
    }

    // Check description
    if (model.description !== data.description) {
      updateData.set('description', data.description || '')
      needUpdate = true
    }

    // Check name and path
    if (
      model.subFolder !== data.subFolder ||
      model.pathIndex !== data.pathIndex ||
      model.basename !== data.basename ||
      model.type !== data.type ||
      model.extension !== data.extension
    ) {
      oldKey = genModelKey(model)
      updateData.set('type', data.type)
      updateData.set('pathIndex', String(data.pathIndex))
      updateData.set('fullname', genModelFullName(data as BaseModel))
      updateData.set('extension', data.extension || '')
      needUpdate = true
    }

    if (!needUpdate) {
      console.log('No changes to update for model:', model.basename)
      return
    }

    loading.show('updateModel')
    try {
      const url = genModelUrl(model)
      console.log('Updating model:', { url, data: Object.fromEntries(updateData) })
      const response = await request(url, {
        method: 'PUT',
        body: updateData,
      })
      if (!response.success) {
        throw new Error(response.error || t('updateModelFailed'))
      }
      if (oldKey) {
        store.dialog.close({ key: oldKey })
      }
      await refreshModels(data.type)
      console.log(t('success'), t('modelUpdated', { name: data.basename }))
    } catch (error) {
      console.error(t('error'), error.message || t('updateModelFailed'))
      throw error
    } finally {
      loading.hide('updateModel')
    }
  }

  const deleteModel = async (model: BaseModel) => {
    return new Promise((resolve) => {
      console.log(t('deleteAsk', [t('model').toLowerCase()]))
      const accept = async () => {
        const dialogKey = genModelKey(model)
        loading.show('deleteModel')
        try {
          const response = await request(genModelUrl(model), {
            method: 'DELETE',
          })
          if (!response.success) {
            throw new Error(response.error || t('deleteModelFailed'))
          }
          console.log(t('success'), t('modelDeleted', { name: model.basename }))
          store.dialog.close({ key: dialogKey })
          await refreshModels(model.type)
          resolve(void 0)
        } catch (error) {
          console.error(t('error'), error.message || t('deleteModelFailed'))
          resolve(void 0)
        } finally {
          loading.hide('deleteModel')
        }
      }
      const reject = () => {
        resolve(void 0)
      }
      accept()
    })
  }

  function openModelDetail(model: BaseModel) {
    const dialogKey = genModelKey(model)
    const filename = model.basename.replace(model.extension || '', '')

    if (store.dialog.isOpen?.({ key: dialogKey })) {
      console.warn(t('warning'), t('modelDetailsOpen'))
      return
    }

    store.dialog.open({
      key: dialogKey,
      title: filename,
      content: DialogModelDetail,
      contentProps: { model },
    })
  }

  function getFullPath(model: BaseModel) {
    const fullname = genModelFullName(model)
    const prefixPath = folders.value[model.type]?.[model.pathIndex] || ''
    return [prefixPath, fullname].filter(Boolean).join('/')
  }

  const handleScanUpdate = ({
    task_id,
    file,
  }: {
    task_id: string
    file: Model
  }) => {
    for (const folder in scanTasks.value) {
      if (scanTasks.value[folder].taskId === task_id) {
        models.value[folder] = [...(models.value[folder] || []), file]
      }
    }
  }

  const handleScanComplete = ({
    task_id,
    results,
  }: {
    task_id: string
    results: Model[]
  }) => {
    for (const folder in scanTasks.value) {
      if (scanTasks.value[folder].taskId === task_id) {
        models.value[folder] = results
        scanTasks.value[folder].status = 'completed'
        loading.hide(`scan-${folder}`)
      }
    }
  }

  const handleScanError = ({
    task_id,
    error,
  }: {
    task_id: string
    error: string
  }) => {
    for (const folder in scanTasks.value) {
      if (scanTasks.value[folder].taskId === task_id) {
        scanTasks.value[folder].status = 'failed'
        scanTasks.value[folder].error = error
        console.error(
          t('error'),
          t('scanFailed', { error: error || 'Unknown', folder }),
        )
        loading.hide(`scan-${folder}`)
      }
    }
  }

  onMounted(() => {
    store.on('scan:update', handleScanUpdate)
    store.on('scan:complete', handleScanComplete)
    store.on('scan:error', handleScanError)
  })

  onUnmounted(() => {
    store.off('scan:update', handleScanUpdate)
    store.off('scan:complete', handleScanComplete)
    store.off('scan:error', handleScanError)
  })

  return {
    initialized,
    folders,
    data: models,
    scanTasks,
    refresh: refreshAllModels,
    remove: deleteModel,
    update: updateModel,
    download: downloadModel,
    openModelDetail,
    getFullPath,
  }
})

declare module 'hooks/store' {
  interface StoreProvider {
    models: ReturnType<typeof useModels>
  }
}

export const useModelFormData = (
  getFormData: () => BaseModel | VersionModel,
) => {
  const formData = ref<BaseModel | VersionModel>(getFormData())
  const modelData = ref<BaseModel | VersionModel>(getFormData())

  type ResetCallback = () => void
  const resetCallback = ref<ResetCallback[]>([])

  const registerReset = (callback: ResetCallback) => {
    resetCallback.value.push(callback)
  }

  const reset = () => {
    formData.value = getFormData()
    modelData.value = getFormData()
    for (const callback of resetCallback.value) {
      callback()
    }
  }

  type SubmitCallback = (data: WithResolved<BaseModel | VersionModel>) => void
  const submitCallback = ref<SubmitCallback[]>([])

  const registerSubmit = (callback: SubmitCallback) => {
    submitCallback.value.push(callback)
  }

  const submit = (): WithResolved<BaseModel | VersionModel> => {
    const data: any = cloneDeep(toRaw(unref(formData)))
    for (const callback of submitCallback.value) {
      callback(data)
    }
    return data
  }

  const metadata = ref<Record<string, any>>({})

  return {
    formData,
    modelData,
    registerReset,
    reset,
    registerSubmit,
    submit,
    metadata,
  }
}

type ModelFormInstance = ReturnType<typeof useModelFormData>

/**
 * Model base info
 */
const baseInfoKey = Symbol('baseInfo') as InjectionKey<
  ReturnType<typeof useModelBaseInfoEditor>
>

export const useModelBaseInfoEditor = (formInstance: ModelFormInstance) => {
  const { formData: model, modelData } = formInstance
  const { t } = useI18n()

  const provideModelFolders = inject(modelFolderProvideKey)
  const modelFolders = computed<ModelFolder>(() => {
    return provideModelFolders?.value ?? {}
  })

  const type = computed({
    get: () => {
      return model.value.type || ''
    },
    set: (val) => {
      model.value.type = val
    },
  })

  const pathIndex = computed({
    get: () => {
      return model.value.pathIndex ?? 0
    },
    set: (val) => {
      model.value.pathIndex = val
    },
  })

  const subFolder = computed({
    get: () => {
      return model.value.subFolder || ''
    },
    set: (val) => {
      model.value.subFolder = val
    },
  })

  const extension = computed({
    get: () => {
      return model.value.extension || ''
    },
    set: (val) => {
      model.value.extension = val
    },
  })

  const basename = computed({
    get: () => {
      return model.value.basename || ''
    },
    set: (val) => {
      model.value.basename = val
    },
  })

  interface BaseInfoItem {
    key: string
    display: string
    value: any
  }

  interface FieldsItem {
    key: keyof Model
    formatter: (val: any) => string | undefined | null
  }

  const baseInfo = computed(() => {
    const fields: FieldsItem[] = [
      {
        key: 'type',
        formatter: () =>
          modelData.value.type in modelFolders.value
            ? modelData.value.type
            : undefined,
      },
      {
        key: 'pathIndex',
        formatter: () => {
          const modelType = model.value.type
          const pathIndex = model.value.pathIndex ?? 0
          if (!modelType) {
            return t('noFolderSelected')
          }
          const folders = modelFolders.value[modelType] ?? []
          return [`${folders[pathIndex] || ''}`, model.value.subFolder]
            .filter(Boolean)
            .join('/')
        },
      },
      {
        key: 'basename',
        formatter: (val) => `${val}${model.value.extension || ''}`,
      },
      {
        key: 'sizeBytes',
        formatter: (val) => (val == null ? t('unknown') : bytesToSize(val)),
      },
      {
        key: 'createdAt',
        formatter: (val) => val && formatDate(val),
      },
      {
        key: 'updatedAt',
        formatter: (val) => val && formatDate(val),
      },
    ]

    const information: Record<string, BaseInfoItem> = {}
    for (const item of fields) {
      const key = item.key
      const value = model.value[key]
      const display = item.formatter(value)

      if (display) {
        information[key] = { key, value, display }
      }
    }

    return information
  })

  const result = {
    type,
    baseInfo,
    basename,
    extension,
    subFolder,
    pathIndex,
    modelFolders,
  }

  provide(baseInfoKey, result)

  return result
}

export const useModelBaseInfo = () => {
  const result = inject(baseInfoKey)
  if (!result) {
    throw new Error(t('baseInfoProviderMissing'))
  }
  return result
}

export const useModelFolder = (
  option: {
    type?: MaybeRefOrGetter<string | undefined>
    models?: Ref<Model[]> // Optional: Use external model list (e.g., from DialogScanning.vue)
  } = {},
) => {
  const { data: storeModels, folders: modelFolders } = useModels()

  const pathOptions = computed(() => {
    const type = toValue(option.type)
    if (!type) {
      return []
    }

    const folderItems = cloneDeep(
      option.models?.value || storeModels.value[type] || [],
    )
    const pureFolders = folderItems.filter((item) => item.isFolder)
    pureFolders.sort((a, b) => a.basename.localeCompare(b.basename))

    const folders = modelFolders.value[type] ?? []

    const root: TreeNode[] = []

    for (const [index, folder] of folders.entries()) {
      const pathIndexItem: TreeNode = {
        key: folder,
        label: folder,
        children: [],
      }

      const items = pureFolders
        .filter((item) => item.pathIndex === index)
        .map((item) => {
          const node: TreeNode = {
            key: `${folder}/${genModelFullName(item)}`,
            label: item.basename,
            data: item,
          }
          return node
        })
      const itemMap = Object.fromEntries(items.map((item) => [item.key, item]))

      for (const item of items) {
        const key = item.key
        const parentKey = key.split('/').slice(0, -1).join('/')

        if (parentKey === folder) {
          pathIndexItem.children!.push(item)
          continue
        }

        const parentItem = itemMap[parentKey]
        if (parentItem) {
          parentItem.children ??= []
          parentItem.children.push(item)
        }
      }

      root.push(pathIndexItem)
    }

    return root
  })

  return {
    pathOptions,
  }
}

/**
 * Editable preview image.
 */
const previewKey = Symbol('preview') as InjectionKey<
  ReturnType<typeof useModelPreviewEditor>
>

const PREVIEW_TYPE_OPTIONS = ['default', 'network', 'local', 'none'] as const

export const useModelPreviewEditor = (formInstance: ModelFormInstance) => {
  const { formData: model, registerReset, registerSubmit } = formInstance
  const { t } = useI18n()

  const typeOptions = PREVIEW_TYPE_OPTIONS
  const currentType = ref<(typeof PREVIEW_TYPE_OPTIONS)[number]>('default')

  const defaultContent = computed(() => {
    return model.value.preview ? castArray(model.value.preview) : []
  })
  const defaultContentPage = ref(0)

  const networkContent = ref<string | null>(null)

  const localContent = ref<string | null>(null)
  const updateLocalContent = async (event: SelectEvent) => {
    const { files } = event
    localContent.value = files[0].objectURL
  }

  const noPreviewContent = computed(() => {
    const folder = model.value.type || 'unknown'
    return `/preview/${folder}/0/no-preview.png`
  })

  const preview = computed({
    get: () => {
      let content: string | null | undefined

      switch (currentType.value) {
        case 'default':
          content = defaultContent.value[defaultContentPage.value]
          break
        case 'network':
          content = networkContent.value
          break
        case 'local':
          content = localContent.value
          break
        default:
          content = null
          break
      }

      return content
    },
    set: (val) => {
      if (currentType.value === 'network') {
        networkContent.value = val
      } else if (currentType.value === 'local') {
        localContent.value = val
      }
    },
  })

  const previewType = computed({
    get: () => {
      return model.value.previewType || 'none'
    },
    set: (val: 'image' | 'video' | 'none') => {
      model.value.previewType = val
    },
  })

  onMounted(() => {
    registerReset(() => {
      currentType.value = 'default'
      defaultContentPage.value = 0
      networkContent.value = null
      localContent.value = null
    })

    registerSubmit((data) => {
      data.preview = preview.value
      data.previewType = previewType.value
    })
  })

  const result = {
    preview,
    previewType,
    typeOptions,
    currentType,
    defaultContent,
    defaultContentPage,
    networkContent,
    localContent,
    updateLocalContent,
    noPreviewContent,
  }

  provide(previewKey, result)

  return result
}

export const useModelPreview = () => {
  const result = inject(previewKey)
  if (!result) {
    throw new Error(t('previewProviderMissing'))
  }
  return result
}

/**
 * Model description
 */
const descriptionKey = Symbol('description') as InjectionKey<
  ReturnType<typeof useModelDescriptionEditor>
>

export const useModelDescriptionEditor = (formInstance: ModelFormInstance) => {
  const { formData: model, metadata } = formInstance
  const { t } = useI18n()

  const md = useMarkdown({ metadata: metadata.value })

  const description = computed({
    get: () => {
      return model.value.description || ''
    },
    set: (val) => {
      model.value.description = val
    },
  })

  const renderedDescription = computed(() => {
    return description.value ? md.render(description.value) : ''
  })

  const result = { renderedDescription, description }

  provide(descriptionKey, result)

  return result
}

export const useModelDescription = () => {
  const result = inject(descriptionKey)
  if (!result) {
    throw new Error(t('descriptionProviderMissing'))
  }
  return result
}

/**
 * Model metadata
 */
const metadataKey = Symbol('metadata') as InjectionKey<
  ReturnType<typeof useModelMetadataEditor>
>

export const useModelMetadataEditor = (formInstance: ModelFormInstance) => {
  const { formData: model } = formInstance
  const { t } = useI18n()

  const metadata = computed(() => {
    return model.value.metadata || {}
  })

  const result = { metadata }

  provide(metadataKey, result)

  return result
}

export const useModelMetadata = () => {
  const result = inject(metadataKey)
  if (!result) {
    throw new Error(t('metadataProviderMissing'))
  }
  return result
}

export const useModelNodeAction = () => {
  const { t } = useI18n()

  const createNode = (model: BaseModel, options: Record<string, any> = {}) => {
    const nodeType = resolveModelTypeLoader(model.type)
    if (!nodeType) {
      throw new Error(t('unSupportedModelType', [model.type]))
    }

    const node = window.LiteGraph.createNode(nodeType, null, options)
    const widgetIndex = node.widgets.findIndex((w) => w.type === 'combo')
    if (widgetIndex > -1) {
      node.widgets[widgetIndex].value = genModelFullName(model)
    }
    return node
  }

  const dragToAddModelNode = (model: BaseModel, event: DragEvent) => {
    try {
      const removeEmbeddingExtension = true
      const strictDragToAdd = false

      ModelGrid.dragAddModel(
        event,
        model.type,
        genModelFullName(model),
        removeEmbeddingExtension,
        strictDragToAdd,
      )
    } catch (error) {
      console.error(t('error'), error.message || t('dragAddModelFailed'))
    }
  }

  const addModelNode = (model: BaseModel) => {
    try {
      const selectedNodes = app.canvas.selected_nodes
      const firstSelectedNode = Object.values(selectedNodes)[0]
      const offset = 25
      const pos = firstSelectedNode
        ? [firstSelectedNode.pos[0] + offset, firstSelectedNode.pos[1] + offset]
        : app.canvas.canvas_mouse
      const node = createNode(model, { pos })
      app.graph.add(node)
      app.canvas.selectNode(node)
    } catch (error) {
      console.error(t('error'), error.message || t('addModelNodeFailed'))
    }
  }

  const copyModelNode = (model: BaseModel) => {
    try {
      const node = createNode(model)
      app.canvas.copyToClipboard([node])
      console.log(t('success'), t('modelCopied'))
    } catch (error) {
      console.error(t('error'), error.message || t('copyModelFailed'))
    }
  }

  const loadPreviewWorkflow = async (model: BaseModel) => {
    try {
      const previewUrl = model.preview as string
      if (!previewUrl) {
        throw new Error(t('noPreviewAvailable'))
      }
      const response = await fetch(previewUrl)
      const data = await response.blob()
      const type = data.type
      const extension = type.split('/').pop()
      const file = new File([data], `${model.basename}.${extension}`, { type })
      app.handleFile(file)
    } catch (error) {
      console.error(t('error'), error.message || t('loadPreviewFailed'))
    }
  }

  return {
    addModelNode,
    dragToAddModelNode,
    copyModelNode,
    loadPreviewWorkflow,
  }
}
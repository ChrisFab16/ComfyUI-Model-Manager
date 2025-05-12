import DialogModelDetail from 'components/DialogModelDetail.vue'
import { useLoading } from 'hooks/loading'
import { useMarkdown } from 'hooks/markdown'
import { useRequest } from 'hooks/request'
import { defineStore } from 'hooks/store'
import { useToast } from 'hooks/toast'
import { castArray, cloneDeep } from 'lodash'
import { TreeNode } from 'primevue/treenode'
import { app } from 'scripts/comfyAPI'
import { BaseModel, Model, SelectEvent, WithResolved } from 'types/typings'
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
  type Ref,
  ref,
  toRaw,
  toValue,
  unref,
} from 'vue'
import { useI18n } from 'vue-i18n'
import { configSetting } from './config'

type ModelFolder = Record<string, string[]>

const modelFolderProvideKey = Symbol('modelFolder') as InjectionKey<
  Ref<ModelFolder>
>

export const genModelFullName = (model: BaseModel) => {
  const filename = `${model.basename}${model.extension || ''}`
  return [model.subFolder, filename].filter(Boolean).join('/')
}

export const genModelUrl = (model: BaseModel) => {
  const fullname = genModelFullName(model)
  return `/model-manager/model/${model.type}/${model.pathIndex}/${fullname}`
}

export const useModels = defineStore('models', (store) => {
  const { toast, confirm } = useToast()
  const { t } = useI18n()
  const { request } = useRequest()
  const loading = useLoading()

  const folders = ref<ModelFolder>({})
  const initialized = ref(false)
  const models = ref<Record<string, Model[]>>({})
  const scanTasks = ref<Record<string, { taskId: string; status: string; error: string | null }>>({})

  const refreshFolders = async () => {
    try {
      const response = await request('/model-manager/models')
      if (!response.success) {
        throw new Error(response.error || 'Failed to fetch model folders')
      }
      folders.value = response.data
      initialized.value = true
    } catch (error) {
      toast.add({
        severity: 'error',
        summary: 'Error',
        detail: error.message || 'Failed to fetch model folders',
        life: 5000,
      })
    }
  }

  provide(modelFolderProvideKey, folders)

  const refreshModels = async (folder: string) => {
    if (!folder || scanTasks.value[folder]?.status === 'running') return

    if (!(folder in folders.value)) {
      toast.add({
        severity: 'error',
        summary: 'Error',
        detail: `Invalid model type: ${folder}`,
        life: 5000,
      })
      return
    }

    loading.show(folder)
    try {
      const response = await request(`/model-manager/scan/start?folder=${folder}`)
      if (!response.success) {
        throw new Error(response.error || 'Failed to start scan')
      }
      const { taskId } = response
      scanTasks.value[folder] = { taskId, status: 'running', error: null }
    } catch (error) {
      toast.add({
        severity: 'error',
        summary: 'Error',
        detail: error.message || 'Failed to start model scan',
        life: 5000,
      })
      loading.hide(folder)
    }
  }

  const refreshAllModels = async (force = false) => {
    const forceRefresh = force ? refreshFolders() : Promise.resolve()
    models.value = {}
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
            try {
              await refreshModels(folder)
            } catch (error) {
              toast.add({
                severity: 'error',
                summary: 'Error',
                detail: `Failed to refresh models for ${folder}: ${error.message || 'Unknown error'}`,
                life: 5000,
              })
              throw error
            }
          }),
      ),
    )
    const failures = results.filter((r) => r.status === 'rejected').length
    if (failures > 0) {
      toast.add({
        severity: 'warn',
        summary: 'Partial Failure',
        detail: `Failed to refresh ${failures} model types`,
        life: 5000,
      })
    }
  }

  const updateModel = async (
    model: BaseModel,
    data: WithResolved<BaseModel>,
    formData?: FormData,
  ) => {
    const updateData = formData || new FormData()
    let oldKey: string | null = null
    let needUpdate = false

    // Validate inputs
    if (!data.type || !(data.type in folders.value)) {
      toast.add({
        severity: 'error',
        summary: 'Validation Error',
        detail: 'Invalid model type',
        life: 5000,
      })
      return
    }
    if (!data.basename) {
      toast.add({
        severity: 'error',
        summary: 'Validation Error',
        detail: 'Model name is required',
        life: 5000,
      })
      return
    }
    const invalidChars = /[\\/:*?"<>|]/
    if (invalidChars.test(data.basename)) {
      toast.add({
        severity: 'error',
        summary: 'Validation Error',
        detail: 'Model name contains invalid characters: \\ / : * ? " < > |',
        life: 5000,
      })
      return
    }
    if (data.pathIndex < 0 || data.pathIndex >= (folders.value[data.type]?.length || 0)) {
      toast.add({
        severity: 'error',
        summary: 'Validation Error',
        detail: 'Invalid path index',
        life: 5000,
      })
      return
    }

    // Check preview
    if (model.preview !== data.preview) {
      if (data.preview) {
        const previewFile = await previewUrlToFile(data.preview as string)
        updateData.set('previewFile', previewFile)
      } else {
        updateData.set('previewFile', 'undefined')
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
      return
    }

    loading.show()
    try {
      const response = await request(genModelUrl(model), {
        method: 'PUT',
        body: updateData,
      })
      if (!response.success) {
        throw new Error(response.error || 'Failed to update model')
      }
      if (oldKey) {
        store.dialog.close({ key: oldKey })
      }
      await refreshModels(data.type)
      toast.add({
        severity: 'success',
        summary: 'Success',
        detail: `Model ${data.basename} updated`,
        life: 2000,
      })
    } catch (error) {
      toast.add({
        severity: 'error',
        summary: 'Error',
        detail: error.message || 'Failed to update model',
        life: 5000,
      })
    } finally {
      loading.hide()
    }
  }

  const deleteModel = async (model: BaseModel) => {
    return new Promise((resolve) => {
      confirm.require({
        message: t('deleteAsk', [t('model').toLowerCase()]),
        header: 'Danger',
        icon: 'pi pi-info-circle',
        rejectProps: {
          label: t('cancel'),
          severity: 'secondary',
          outlined: true,
        },
        acceptProps: {
          label: t('delete'),
          severity: 'danger',
        },
        accept: async () => {
          const dialogKey = genModelKey(model)
          loading.show()
          try {
            const response = await request(genModelUrl(model), {
              method: 'DELETE',
            })
            if (!response.success) {
              throw new Error(response.error || 'Failed to delete model')
            }
            toast.add({
              severity: 'success',
              summary: 'Success',
              detail: `${model.basename} deleted`,
              life: 2000,
            })
            store.dialog.close({ key: dialogKey })
            await refreshModels(model.type)
            resolve(void 0)
          } catch (error) {
            toast.add({
              severity: 'error',
              summary: 'Error',
              detail: error.message || 'Failed to delete model',
              life: 5000,
            })
            resolve(void 0)
          } finally {
            loading.hide()
          }
        },
        reject: () => {
          resolve(void 0)
        },
      })
    })
  }

  function openModelDetail(model: BaseModel) {
    const dialogKey = genModelKey(model)
    const filename = model.basename.replace(model.extension || '', '')

    // Prevent duplicate dialogs
    if (store.dialog.isOpen?.({ key: dialogKey })) {
      toast.add({
        severity: 'warn',
        summary: 'Warning',
        detail: 'Model details already open',
        life: 2000,
      })
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

  const handleScanUpdate = ({ task_id, file }: { task_id: string; file: Model }) => {
    for (const folder in scanTasks.value) {
      if (scanTasks.value[folder].taskId === task_id) {
        models.value[folder] = [...(models.value[folder] || []), file]
      }
    }
  }

  const handleScanComplete = ({ task_id, results }: { task_id: string; results: Model[] }) => {
    for (const folder in scanTasks) {
      if (scanTasks.value[folder].taskId === task_id) {
        models.value[folder] = results
        scanTasks.value[folder].status = 'completed'
        loading.hide(folder)
      }
    }
  }

  const handleScanError = ({ task_id, error }: { task_id: string; error: string }) => {
    for (const folder in scanTasks.value) {
      if (scanTasks.value[folder].taskId === task_id) {
        scanTasks.value[folder].status = 'failed'
        scanTasks.value[folder].error = error
        toast.add({
          severity: 'error',
          summary: 'Error',
          detail: error || 'Model scan failed',
          life: 5000,
        })
        loading.hide(folder)
      }
    }
  }

  onMounted(() => {
    storeEvent.on('scan:update', handleScanUpdate)
    storeEvent.on('scan:complete', handleScanComplete)
    storeEvent.on('scan:error', handleScanError)
  })

  onUnmounted(() => {
    storeEvent.off('scan:update', handleScanUpdate)
    storeEvent.off('scan:complete', handleScanComplete)
    storeEvent.off('scan:error', handleScanError)
  })

  return {
    initialized,
    folders,
    data: models,
    scanTasks,
    refresh: refreshAllModels,
    remove: deleteModel,
    update: updateModel,
    openModelDetail,
    getFullPath,
  }
})

declare module 'hooks/store' {
  interface StoreProvider {
    models: ReturnType<typeof useModels>
  }
}

export const useModelFormData = (getFormData: () => BaseModel) => {
  const formData = ref<BaseModel>(getFormData())
  const modelData = ref<BaseModel>(getFormData())

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

  type SubmitCallback = (data: WithResolved<BaseModel>) => void
  const submitCallback = ref<SubmitCallback[]>([])

  const registerSubmit = (callback: SubmitCallback) => {
    submitCallback.value.push(callback)
  }

  const submit = (): WithResolved<BaseModel> => {
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
            return undefined
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
        formatter: (val) => (val == null ? 'Unknown' : bytesToSize(val)),
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
    throw new Error('useModelBaseInfo must be used within a ModelBaseInfoEditor provider')
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
  const isLoading = ref(false)

  const pathOptions = computed(() => {
    const type = toValue(option.type)
    if (!type) {
      return []
    }

    // Use provided models (e.g., scanModelsList) or store models
    const folderItems = cloneDeep(option.models?.value || storeModels.value[type] || [])
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

  const handleScanUpdate = ({ file }: { task_id: string; file: Model }) => {
    if (file.type === toValue(option.type)) {
      isLoading.value = true
      setTimeout(() => (isLoading.value = false), 1000) // Debounce UI update
    }
  }

  const handleScanComplete = ({ results }: { task_id: string; results: Model[] }) => {
    if (results.some((m) => m.type === toValue(option.type))) {
      isLoading.value = true
      setTimeout(() => (isLoading.value = false), 1000)
    }
  }

  onMounted(() => {
    storeEvent.on('scan:update', handleScanUpdate)
    storeEvent.on('scan:complete', handleScanComplete)
  })

  onUnmounted(() => {
    storeEvent.off('scan:update', handleScanUpdate)
    storeEvent.off('scan:complete', handleScanComplete)
  })

  return {
    pathOptions,
    isLoading,
  }
}

/**
 * Editable preview image.
 */
const previewKey = Symbol('preview') as InjectionKey<
  ReturnType<typeof useModelPreviewEditor>
>

export const useModelPreviewEditor = (formInstance: ModelFormInstance) => {
  const { formData: model, registerReset, registerSubmit } = formInstance

  const typeOptions = ref(['default', 'network', 'local', 'none'])
  const currentType = ref('default')

  /**
   * Default images
   */
  const defaultContent = computed(() => {
    return model.value.preview ? castArray(model.value.preview) : []
  })
  const defaultContentPage = ref(0)

  /**
   * Network picture url
   */
  const networkContent = ref<string | null>(null)

  /**
   * Local file url
   */
  const localContent = ref<string | null>(null)
  const updateLocalContent = async (event: SelectEvent) => {
    const { files } = event
    localContent.value = files[0].objectURL
  }

  /**
   * No preview
   */
  const noPreviewContent = computed(() => {
    const folder = model.value.type || 'unknown'
    return `/model-manager/preview/${folder}/0/no-preview.png`
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
    throw new Error('useModelPreview must be used within a ModelPreviewEditor provider')
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
    throw new Error('useModelDescription must be used within a ModelDescriptionEditor provider')
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
    throw new Error('useModelMetadata must be used within a ModelMetadataEditor provider')
  }
  return result
}

export const useModelNodeAction = () => {
  const { t } = useI18n()
  const { toast, wrapperToastError } = useToast()

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

  const dragToAddModelNode = wrapperToastError(
    (model: BaseModel, event: DragEvent) => {
      const removeEmbeddingExtension = true
      const strictDragToAdd = false

      ModelGrid.dragAddModel(
        event,
        model.type,
        genModelFullName(model),
        removeEmbeddingExtension,
        strictDragToAdd,
      )
    },
  )

  const addModelNode = wrapperToastError((model: BaseModel) => {
    const selectedNodes = app.canvas.selected_nodes
    const firstSelectedNode = Object.values(selectedNodes)[0]
    const offset = 25
    const pos = firstSelectedNode
      ? [firstSelectedNode.pos[0] + offset, firstSelectedNode.pos[1] + offset]
      : app.canvas.canvas_mouse
    const node = createNode(model, { pos })
    app.graph.add(node)
    app.canvas.selectNode(node)
  })

  const copyModelNode = wrapperToastError((model: BaseModel) => {
    const node = createNode(model)
    app.canvas.copyToClipboard([node])
    toast.add({
      severity: 'success',
      summary: 'Success',
      detail: t('modelCopied'),
      life: 2000,
    })
  })

  const loadPreviewWorkflow = wrapperToastError(async (model: BaseModel) => {
    const previewUrl = model.preview as string
    if (!previewUrl) {
      throw new Error('No preview available')
    }
    const response = await fetch(previewUrl)
    const data = await response.blob()
    const type = data.type
    const extension = type.split('/').pop()
    const file = new File([data], `${model.basename}.${extension}`, { type })
    app.handleFile(file)
  })

  return {
    addModelNode,
    dragToAddModelNode,
    copyModelNode,
    loadPreviewWorkflow,
  }
}

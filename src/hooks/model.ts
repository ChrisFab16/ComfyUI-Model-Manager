import DialogModelDetail from 'components/DialogModelDetail.vue'
import { useLoading } from 'hooks/loading'
import { useMarkdown } from 'hooks/markdown'
import { request } from 'hooks/request'
import { defineStore } from 'hooks/store'
import { useToast } from 'hooks/toast'
import { castArray, cloneDeep } from 'lodash'
import { TreeNode } from 'primevue/treenode'
import { api, app } from 'scripts/comfyAPI'
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

    loading.show(folder)
    try {
      const response = await request(`/model-manager/scan/start?folder=${folder}`)
      if (!response.success) {
        throw new Error(response.error || 'Failed to start scan')
      }
      const { taskId } = response
      scanTasks.value[folder] = { taskId, status: 'running', error: null }
      pollScanStatus(folder, taskId)
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

  const pollScanStatus = async (folder: string, taskId: string) => {
    try {
      const response = await request(`/model-manager/scan/status/${taskId}`)
      if (!response.success) {
        throw new Error(response.error || 'Failed to get scan status')
      }
      const { status, data, error } = response
      scanTasks.value[folder] = { taskId, status, error }
      models.value[folder] = data

      if (status === 'running') {
        setTimeout(() => pollScanStatus(folder, taskId), 1000)
      } else if (status === 'failed') {
        toast.add({
          severity: 'error',
          summary: 'Error',
          detail: error || 'Model scan failed',
          life: 5000,
        })
        loading.hide(folder)
      } else if (status === 'completed') {
        loading.hide(folder)
      }
    } catch (error) {
      scanTasks.value[folder] = { taskId, status: 'failed', error: error.message || 'Failed to get scan status' }
      toast.add({
        severity: 'error',
        summary: 'Error',
        detail: error.message || 'Failed to get scan status',
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
    await forceRefresh.then(() =>
      Promise.allSettled(
        Object.keys(folders.value)
          .filter((folder) => !customBlackList.includes(folder))
          .map(refreshModels),
      ),
    )
  }

  const updateModel = async (
    model: BaseModel,
    data: WithResolved<BaseModel>,
  ) => {
    const updateData = new FormData()
    let oldKey: string | null = null
    let needUpdate = false

    // Check current preview
    if (model.preview !== data.preview) {
      const preview = data.preview
      if (preview) {
        const previewFile = await previewUrlToFile(data.preview as string)
        updateData.set('previewFile', previewFile)
      } else {
        updateData.set('previewFile', 'undefined')
      }
      needUpdate = true
    }

    // Check current description
    if (model.description !== data.description) {
      updateData.set('description', data.description || '')
      needUpdate = true
    }

    // Check current name and pathIndex
    if (
      model.subFolder !== data.subFolder ||
      model.pathIndex !== data.pathIndex ||
      model.basename !== data.basename ||
      model.type !== data.type
    ) {
      oldKey = genModelKey(model)
      updateData.set('type', data.type || model.type)
      updateData.set('pathIndex', String(data.pathIndex || model.pathIndex))
      updateData.set('fullname', genModelFullName(data as BaseModel))
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
        accept: () => {
          const dialogKey = genModelKey(model)
          loading.show()
          request(genModelUrl(model), {
            method: 'DELETE',
          })
            .then((response) => {
              if (!response.success) {
                throw new Error(response.error || 'Failed to delete model')
              }
              toast.add({
                severity: 'success',
                summary: 'Success',
                detail: `${model.basename} Deleted`,
                life: 2000,
              })
              store.dialog.close({ key: dialogKey })
              return refreshModels(model.type)
            })
            .then(() => {
              resolve(void 0)
            })
            .catch((error) => {
              toast.add({
                severity: 'error',
                summary: 'Error',
                detail: error.message || 'Failed to delete model',
                life: 5000,
              })
            })
            .finally(() => {
              loading.hide()
            })
        },
        reject: () => {
          resolve(void 0)
        },
      })
    })
  }

  function openModelDetail(model: BaseModel) {
    const filename = model.basename.replace(model.extension, '')

    store.dialog.open({
      key: genModelKey(model),
      title: filename,
      content: DialogModelDetail,
      contentProps: { model: model },
    })
  }

  function getFullPath(model: BaseModel) {
    const fullname = genModelFullName(model)
    const prefixPath = folders.value[model.type]?.[model.pathIndex]
    return [prefixPath, fullname].filter(Boolean).join('/')
  }

  onMounted(() => {
    api.addEventListener('update_scan_task', (event) => {
      const { task_id, file } = event.detail
      for (const folder in scanTasks.value) {
        if (scanTasks.value[folder].taskId === task_id) {
          models.value[folder] = [...(models.value[folder] || []), file]
        }
      }
    })

    api.addEventListener('complete_scan_task', (event) => {
      const { task_id, results } = event.detail
      for (const folder in scanTasks.value) {
        if (scanTasks.value[folder].taskId === task_id) {
          models.value[folder] = results
          scanTasks.value[folder].status = 'completed'
          loading.hide(folder)
        }
      }
    })

    api.addEventListener('error_scan_task', (event) => {
      const { task_id, error } = event.detail
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
    })
  })

  return {
    initialized: initialized,
    folders: folders,
    data: models,
    scanTasks,
    refresh: refreshAllModels,
    remove: deleteModel,
    update: updateModel,
    openModelDetail: openModelDetail,
    getFullPath: getFullPath,
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
      return model.value.type
    },
    set: (val) => {
      model.value.type = val
    },
  })

  const pathIndex = computed({
    get: () => {
      return model.value.pathIndex
    },
    set: (val) => {
      model.value.pathIndex = val
    },
  })

  const subFolder = computed({
    get: () => {
      return model.value.subFolder
    },
    set: (val) => {
      model.value.subFolder = val
    },
  })

  const extension = computed(() => {
    return model.value.extension
  })

  const basename = computed({
    get: () => {
      return model.value.basename
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
          const pathIndex = model.value.pathIndex
          if (!modelType) {
            return undefined
          }
          const folders = modelFolders.value[modelType] ?? []
          return [`${folders[pathIndex]}`, model.value.subFolder]
            .filter(Boolean)
            .join('/')
        },
      },
      {
        key: 'basename',
        formatter: (val) => `${val}${model.value.extension}`,
      },
      {
        key: 'sizeBytes',
        formatter: (val) => (val == 0 ? 'Unknown' : bytesToSize(val)),
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
  return inject(baseInfoKey)!
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
  const networkContent = ref<string>()

  /**
   * Local file url
   */
  const localContent = ref<string>()
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

  const preview = computed(() => {
    let content: string | undefined

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
        content = undefined
        break
    }

    return content
  })

  const previewType = computed(() => {
    return model.value.previewType
  })

  onMounted(() => {
    registerReset(() => {
      currentType.value = 'default'
      defaultContentPage.value = 0
      networkContent.value = undefined
      localContent.value = undefined
    })

    registerSubmit((data) => {
      data.preview = preview.value
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
  return inject(previewKey)!
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
      return model.value.description
    },
    set: (val) => {
      model.value.description = val
    },
  })

  const renderedDescription = computed(() => {
    return description.value ? md.render(description.value) : undefined
  })

  const result = { renderedDescription, description }

  provide(descriptionKey, result)

  return result
}

export const useModelDescription = () => {
  return inject(descriptionKey)!
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
    return model.value.metadata
  })

  const result = { metadata }

  provide(metadataKey, result)

  return result
}

export const useModelMetadata = () => {
  return inject(metadataKey)!
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

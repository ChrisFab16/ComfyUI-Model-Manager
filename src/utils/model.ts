import { BaseModel } from 'types/typings'
import { useToast } from 'hooks/toast'

/**
 * Mapping of model types to ComfyUI node loader types.
 * Corresponds to model types in py/manager.py's MODEL_TYPE_TO_FOLDER.
 */
const loader: Record<string, string | null> = {
  checkpoints: 'CheckpointLoaderSimple',
  loras: 'LoraLoader',
  vae: 'VAELoader',
  clip: 'CLIPLoader',
  diffusion_models: 'UNETLoader',
  unet: 'UNETLoader',
  clip_vision: 'CLIPVisionLoader',
  style_models: 'StyleModelLoader',
  embeddings: null, // Embeddings are not loaded via nodes
  diffusers: 'DiffusersLoader',
  vae_approx: null, // Not used in workflows
  controlnet: 'ControlNetLoader',
  gligen: 'GLIGENLoader',
  upscale_models: 'UpscaleModelLoader',
  hypernetworks: 'HypernetworkLoader',
  photomaker: 'PhotoMakerLoader',
  classifiers: null, // Not used in workflows
  ipadapter: 'IPAdapterLoader',
  t2iadapter: 'T2IAdapterLoader',
  instantid: 'InstantIDLoader',
  animatediff_models: 'AnimateDiffLoader',
  photomaker_stacked: 'PhotoMakerStackedLoader',
  segment_anything: 'SegmentAnythingLoader',
  sam2: 'SAM2Loader',
}

/**
 * Resolves the ComfyUI node loader type for a given model type.
 * @param type The model type (e.g., 'checkpoints', 'loras').
 * @returns The corresponding node loader type (e.g., 'CheckpointLoaderSimple') or null if unsupported.
 * @throws Error if the model type is invalid or unsupported.
 */
export const resolveModelTypeLoader = (type: string): string | null => {
  const { toast } = useToast()

  if (!type || typeof type !== 'string') {
    const errorMessage = 'Model type must be a non-empty string'
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: errorMessage,
      life: 5000,
    })
    throw new Error(errorMessage)
  }

  const nodeType = loader[type]
  if (nodeType === undefined) {
    const errorMessage = `Unsupported model type: ${type}`
    toast.add({
      severity: 'warn',
      summary: 'Warning',
      detail: errorMessage,
      life: 5000,
    })
    throw new Error(errorMessage)
  }

  return nodeType
}

/**
 * Generates a unique key for a model, used for dialog management and state tracking.
 * @param model The model object with type, pathIndex, subFolder, basename, and optional extension.
 * @returns A unique key string (e.g., 'checkpoints:0:subfolder:model.safetensors').
 * @throws Error if required fields are missing or invalid.
 */
export const genModelKey = (model: BaseModel): string => {
  const { toast } = useToast()

  if (!model) {
    const errorMessage = 'Model object is required'
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: errorMessage,
      life: 5000,
    })
    throw new Error(errorMessage)
  }

  const { type, pathIndex, subFolder, basename, extension } = model

  if (!type || typeof type !== 'string') {
    const errorMessage = 'Model type is required and must be a string'
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: errorMessage,
      life: 5000,
    })
    throw new Error(errorMessage)
  }

  if (pathIndex == null || pathIndex < 0) {
    const errorMessage = 'Path index is required and must be a non-negative number'
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: errorMessage,
      life: 5000,
    })
    throw new Error(errorMessage)
  }

  if (!basename || typeof basename !== 'string') {
    const errorMessage = 'Model basename is required and must be a string'
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: errorMessage,
      life: 5000,
    })
    throw new Error(errorMessage)
  }

  // Normalize subFolder and extension
  const normalizedSubFolder = (subFolder || '').replace(/^\/+|\/+$/g, '')
  const normalizedExtension = extension || ''

  return `${type}:${pathIndex}:${normalizedSubFolder}:${basename}${normalizedExtension}`
}

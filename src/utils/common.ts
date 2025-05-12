import dayjs from 'dayjs'
import { useToast } from 'hooks/toast'

export const bytesToSize = (
  bytes: number | string | undefined | null,
  decimals = 2,
): string => {
  if (typeof bytes === 'undefined' || bytes === null) {
    return '0 Bytes'
  }
  if (typeof bytes === 'string') {
    bytes = Number(bytes)
  }
  if (Number.isNaN(bytes) || bytes < 0) {
    return '0 Bytes'
  }
  if (bytes === 0) {
    return '0 Bytes'
  }
  const k = 1024
  const dm = decimals < 0 ? 0 : decimals
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i]
}

export const formatDate = (date: number | string | Date | undefined | null): string => {
  if (!date) {
    return ''
  }
  const parsedDate = dayjs(date)
  if (!parsedDate.isValid()) {
    return ''
  }
  return parsedDate.format('YYYY-MM-DD HH:mm:ss')
}

export const previewUrlToFile = async (url: string, basename?: string): Promise<File> => {
  const { toast } = useToast()

  // Validate URL
  try {
    new URL(url)
  } catch {
    throw new Error('Invalid preview URL')
  }

  // Set fetch timeout (10 seconds)
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), 10000)

  try {
    const response = await fetch(url, { signal: controller.signal })
    clearTimeout(timeoutId)

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }

    const blob = await response.blob()

    // Validate blob is an image
    if (!blob.type.startsWith('image/')) {
      throw new Error('Preview must be an image file')
    }

    const extension = blob.type.split('/')[1] || 'png'
    const filename = basename ? `${basename}_preview.${extension}` : `preview.${extension}`
    const file = new File([blob], filename, { type: blob.type })

    return file
  } catch (error) {
    const errorMessage = error.name === 'AbortError'
      ? 'Preview fetch timed out'
      : error.message || 'Failed to fetch preview image'
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: errorMessage,
      life: 5000,
    })
    throw new Error(errorMessage)
  }
}

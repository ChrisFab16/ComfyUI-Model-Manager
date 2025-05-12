import { useLoading } from 'hooks/loading'
import { api } from 'scripts/comfyAPI'
import { onMounted, ref } from 'vue'
import { useToast } from 'hooks/toast'

interface ApiResponse<T> {
  success: boolean
  data: T
  error: string | null
  status: number
}

export const request = async <T = any>(
  url: string,
  options: RequestInit & { modelManagerPrefix?: boolean } = {},
): Promise<ApiResponse<T>> => {
  const { toast } = useToast()
  const { modelManagerPrefix = true, ...fetchOptions } = options
  const requestUrl = modelManagerPrefix ? `/model-manager${url}` : url

  try {
    const response = await api.fetchApi(requestUrl, {
      ...fetchOptions,
      headers: {
        'Content-Type':
          fetchOptions.body instanceof FormData
            ? 'multipart/form-data'
            : 'application/json',
        ...fetchOptions.headers,
      },
    })

    const resData = await response.json()
    return {
      success: resData.success ?? response.ok,
      data: resData.data ?? resData,
      error: resData.error ?? (response.ok ? null : response.statusText),
      status: response.status,
    }
  } catch (error) {
    const errorMessage = mapErrorMessage(error.message || 'Request failed')
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: errorMessage,
      life: 5000,
    })
    return {
      success: false,
      data: null,
      error: errorMessage,
      status: 0,
    }
  }
}

// Map common backend errors to user-friendly messages
const mapErrorMessage = (error: string): string => {
  switch (true) {
    case error.includes('File already exists'):
      return 'The file already exists in the target location.'
    case error.includes('Authentication required'):
      return 'Authentication is required. Please set your API key.'
    case error.includes('Invalid URL'):
      return 'The provided URL is invalid.'
    case error.includes('Not found'):
      return 'The requested resource was not found.'
    case error.includes('Network error'):
      return 'A network error occurred. Please check your connection.'
    default:
      return error || 'An unexpected error occurred.'
  }
}

export interface RequestOptions<T> {
  method?: RequestInit['method']
  headers?: RequestInit['headers']
  defaultParams?: Record<string, any>
  defaultValue?: any
  postData?: (data: T) => T
  manual?: boolean
  modelManagerPrefix?: boolean
  loadingKey?: string
}

export const useRequest = <T = any>(
  url: string,
  options: RequestOptions<T> = {},
) => {
  const loading = useLoading()
  const { toast } = useToast()
  const postData = options.postData ?? ((data: T) => data)

  const data = ref<T>(options.defaultValue)
  const lastParams = ref()
  const error = ref<string | null>(null)

  const fetch = async (
    params: Record<string, any> = options.defaultParams ?? {},
    fetchOptions: RequestInit = {},
  ) => {
    const loadingKey = options.loadingKey || url
    loading.show(loadingKey)
    error.value = null

    lastParams.value = params

    let requestUrl = url
    const requestOptions: RequestInit = {
      method: options.method || 'GET',
      headers: options.headers,
      ...fetchOptions,
    }
    const requestParams = { ...params }

    // Handle URL template parameters (e.g., /download/{taskId})
    const templatePattern = /\{(.*?)\}/g
    const urlParamKeyMatches = requestUrl.matchAll(templatePattern)
    for (const urlParamKey of urlParamKeyMatches) {
      const [match, paramKey] = urlParamKey
      if (paramKey in requestParams) {
        const paramValue = requestParams[paramKey]
        delete requestParams[paramKey]
        requestUrl = requestUrl.replace(match, paramValue)
      }
    }

    // Set body for non-GET requests
    if (requestOptions.method !== 'GET' && requestParams && !(requestOptions.body instanceof FormData)) {
      requestOptions.body = JSON.stringify(requestParams)
    }

    try {
      const response = await request<T>(requestUrl, {
        ...requestOptions,
        modelManagerPrefix: options.modelManagerPrefix ?? true,
      })

      if (response.success) {
        data.value = postData(response.data)
      } else {
        error.value = mapErrorMessage(response.error || 'Request failed')
        toast.add({
          severity: 'error',
          summary: 'Error',
          detail: error.value,
          life: 5000,
        })
      }
      return response
    } catch (err) {
      error.value = mapErrorMessage(err.message || 'Request failed')
      toast.add({
        severity: 'error',
        summary: 'Error',
        detail: error.value,
        life: 5000,
      })
      return {
        success: false,
        data: null,
        error: error.value,
        status: 0,
      }
    } finally {
      loading.hide(loadingKey)
    }
  }

  onMounted(() => {
    if (!options.manual) {
      fetch()
    }
  })

  const refresh = async () => {
    return fetch(lastParams.value)
  }

  return { data, error, refresh, fetch }
}

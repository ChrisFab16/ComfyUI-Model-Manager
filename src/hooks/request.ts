// src/hooks/request.ts
import { useLoading } from 'hooks/loading'
import { api } from 'scripts/comfyAPI'
import { onMounted, ref } from 'vue'

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
  const { modelManagerPrefix = true, ...fetchOptions } = options
  console.log('request: url=', url, 'modelManagerPrefix=', modelManagerPrefix)
  if (!url) {
    console.error('request: URL is undefined or empty')
    throw new Error('Request URL is undefined')
  }
  const requestUrl = modelManagerPrefix
    ? `/model-manager${url.startsWith('/') ? url : '/' + url}`
    : `/api${url.startsWith('/') ? url : '/' + url}`
  console.log('request: requestUrl=', requestUrl)

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
    console.error('request: error=', errorMessage)
    return {
      success: false,
      data: null,
      error: errorMessage,
      status: 0,
    }
  }
}

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
  const postData = options.postData ?? ((data: T) => data)

  const data = ref<T>(options.defaultValue)
  const lastParams = ref()
  const error = ref<string | null>(null)

  const fetch = async (
    params: Record<string, any> = options.defaultParams ?? {},
    fetchOptions: RequestInit = {},
  ) => {
    console.log('useRequest: fetch url=', url, 'params=', params)
    if (!url) {
      console.error('useRequest: Skipping fetch due to undefined url')
      return { success: false, data: null, error: 'Undefined URL', status: 0 }
    }
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

    if (
      requestOptions.method !== 'GET' &&
      requestParams &&
      !(requestOptions.body instanceof FormData)
    ) {
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
        console.error('useRequest: error=', error.value)
      }
      return response
    } catch (err) {
      error.value = mapErrorMessage(err.message || 'Request failed')
      console.error('useRequest: error=', err.message)
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
    if (!options.manual && url) {
      console.log('useRequest: auto-fetch url=', url)
      fetch()
    } else {
      console.log(
        'useRequest: Skipping auto-fetch, url=',
        url,
        'manual=',
        options.manual,
      )
    }
  })

  const refresh = async () => {
    console.log('useRequest: refresh url=', url)
    return fetch(lastParams.value)
  }

  return { data, error, refresh, fetch }
}

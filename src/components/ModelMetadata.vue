<template>
  <table v-if="dataSource.length" class="w-full border-collapse border">
    <tbody>
      <tr v-for="item in dataSource" :key="item.key" class="h-8 border-b">
        <td class="border-r bg-gray-300 px-4 dark:bg-gray-800">
          {{ formatKey(item.key) }}
        </td>
        <td class="break-all px-4">{{ formatValue(item.value) }}</td>
      </tr>
    </tbody>
  </table>

  <div v-else class="flex flex-col items-center gap-2 py-5">
    <i class="pi pi-info-circle text-lg"></i>
    <div>no metadata</div>
  </div>
</template>

<script setup lang="ts">
import { useModelMetadata } from 'hooks/model'
import { computed } from 'vue'

const { metadata } = useModelMetadata()

const dataSource = computed(() => {
  const dataSource: { key: string; value: any }[] = []
  const flattenObject = (obj: any, prefix = '') => {
    for (const key in obj) {
      if (Object.prototype.hasOwnProperty.call(obj, key)) {
        const value = obj[key]
        if (
          value !== null &&
          typeof value === 'object' &&
          !Array.isArray(value) &&
          Object.keys(value).length > 0
        ) {
          flattenObject(value, prefix ? `${prefix}.${key}` : key)
        } else {
          dataSource.push({
            key: prefix ? `${prefix}.${key}` : key,
            value: value
          })
        }
      }
    }
  }

  // Try to parse metadata if it's a string
  let metadataObj = metadata.value
  if (typeof metadataObj === 'string' && metadataObj.trim().startsWith('{')) {
    try {
      metadataObj = JSON.parse(metadataObj)
    } catch (e) {
      // If parsing fails, use the original value
    }
  }

  flattenObject(metadataObj)
  return dataSource
})

const formatKey = (key: string) => {
  return key
    .split('.')
    .map(part => 
      part
        .replace(/([A-Z])/g, ' $1')
        .replace(/^./, str => str.toUpperCase())
    )
    .join(' › ')
}

const formatValue = (value: any) => {
  if (Array.isArray(value)) {
    return value.join(', ')
  }
  if (typeof value === 'boolean') {
    return value ? 'Yes' : 'No'
  }
  return value
}
</script>

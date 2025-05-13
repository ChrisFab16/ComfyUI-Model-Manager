// src/hooks/download.ts
import { useLoading } from 'hooks/loading';
import { useRequest } from 'hooks/request';
import { defineStore } from 'hooks/store';
import { BaseModel, DownloadTask, DownloadTaskOptions, SelectOptions, VersionModel } from 'types/typings';
import { bytesToSize } from 'utils/common';
import { onMounted, onUnmounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

export const useDownload = defineStore('download', (store) => {
  const { t } = useI18n();
  const { request } = useRequest();
  const loading = useLoading();

  const taskList = ref<DownloadTask[]>([]);

  const createTaskItem = (item: DownloadTaskOptions): DownloadTask => {
    const { taskId, fullname, downloadedSize = 0, totalSize = 0, bps = 0, preview, error, ...rest } = item;

    // Validate inputs
    if (!taskId || !fullname) {
      throw new Error('Task ID and fullname are required');
    }
    if (downloadedSize < 0 || totalSize < 0 || bps < 0) {
      throw new Error('Downloaded size, total size, and BPS must be non-negative');
    }

    const progressPercent = totalSize > 0 ? Math.round((downloadedSize / totalSize) * 100) : 0;

    const task: DownloadTask = {
      ...rest,
      taskId,
      fullname,
      preview: preview || '/model-manager/preview/no-preview.png',
      downloadProgress: `${bytesToSize(downloadedSize)} / ${bytesToSize(totalSize)} (${progressPercent}%)`,
      downloadSpeed: `${bytesToSize(bps)}/s`,
      async pauseTask() {
        try {
          const response = await request(`/model-manager/download/${taskId}`, {
            method: 'PUT',
            body: JSON.stringify({ status: 'pause' }),
          });
          if (!response.success) {
            throw new Error(response.error || 'Failed to pause task');
          }
          console.log('Paused', `Paused download for ${fullname}`);
        } catch (error) {
          console.error('Error', error.message || 'Failed to pause task');
        }
      },
      async resumeTask() {
        try {
          const response = await request(`/model-manager/download/${taskId}`, {
            method: 'PUT',
            body: JSON.stringify({ status: 'resume' }),
          });
          if (!response.success) {
            throw new Error(response.error || 'Failed to resume task');
          }
          console.log('Resumed', `Resumed download for ${fullname}`);
        } catch (error) {
          console.error('Error', error.message || 'Failed to resume task');
        }
      },
      async cancelTask() {
        try {
          console.log(t('cancelAsk', [t('downloadTask').toLowerCase()]));
          const response = await request(`/model-manager/download/${taskId}`, {
            method: 'PUT',
            body: JSON.stringify({ status: 'cancel' }),
          });
          if (!response.success) {
            throw new Error(response.error || 'Failed to cancel task');
          }
          taskList.value = taskList.value.filter((task) => task.taskId !== taskId);
          console.log('Cancelled', `Cancelled download for ${fullname}`);
        } catch (error) {
          console.error('Error', error.message || 'Failed to cancel task');
        }
      },
      async deleteTask() {
        try {
          console.log(t('deleteAsk', [t('downloadTask').toLowerCase()]));
          const response = await request(`/model-manager/download/${taskId}`, {
            method: 'DELETE',
          });
          if (!response.success) {
            throw new Error(response.error || 'Failed to delete task');
          }
          taskList.value = taskList.value.filter((task) => task.taskId !== taskId);
          console.log('Deleted', `Deleted download task for ${fullname}`);
        } catch (error) {
          console.error('Error', error.message || 'Failed to delete task');
        }
      },
    };

    return task;
  };

  const refresh = async () => {
    loading.show('downloadTasks');
    try {
      const response = await request('/model-manager/download/task', { method: 'GET' });
      if (!response.success) {
        throw new Error(response.error || 'Failed to fetch tasks');
      }
      taskList.value = response.data.map((item: DownloadTaskOptions) => createTaskItem(item));
      return taskList.value;
    } catch (error) {
      console.error('Error', error.message || 'Failed to fetch download tasks');
      throw error;
    } finally {
      loading.hide('downloadTasks');
    }
  };

  const init = async () => {
    loading.show('downloadSettings');
    try {
      const response = await request('/model-manager/download/init', { method: 'POST' });
      if (!response.success) {
        throw new Error(response.error || 'Failed to initialize download settings');
      }
      store.config.apiKeyInfo.value = response.data;
    } catch (error) {
      console.error('Error', error.message || 'Failed to initialize download settings');
    } finally {
      loading.hide('downloadSettings');
    }
  };

  const handleDownloadUpdate = ({ taskId, ...item }: { taskId: string } & Partial<DownloadTaskOptions>) => {
    const task = taskList.value.find((t) => t.taskId === taskId);
    if (!task) {
      console.warn(`Task ${taskId} not found in taskList`);
      return;
    }
    if (item.error) {
      console.error('Error', item.error);
      item.error = undefined;
    }
    Object.assign(task, createTaskItem({ taskId, ...task, ...item }));
  };

  const handleDownloadComplete = async ({ taskId }: { taskId: string; model?: BaseModel }) => {
    const task = taskList.value.find((item) => item.taskId === taskId);
    taskList.value = taskList.value.filter((item) => item.taskId !== taskId);
    if (task) {
      console.log('Success', `${task.fullname} download completed`);
      await store.models.refresh();
    }
  };

  const handleReconnected = () => {
    refresh();
  };

  onMounted(() => {
    init();
    refresh();
    store.on('download:update', handleDownloadUpdate);
    store.on('download:complete', handleDownloadComplete);
    store.on('reconnected', handleReconnected);
  });

  onUnmounted(() => {
    store.off('download:update', handleDownloadUpdate);
    store.off('download:complete', handleDownloadComplete);
    store.off('reconnected', handleReconnected);
  });

  return { data: taskList, refresh };
});

declare module 'hooks/store' {
  interface StoreProvider {
    download: ReturnType<typeof useDownload>;
  }
}

export const useModelSearch = () => {
  const { t } = useI18n();
  const loading = useLoading();
  const { request } = useRequest();
  const data = ref<(SelectOptions & { item: VersionModel })[]>([]);
  const current = ref<string | number>();
  const currentModel = ref<VersionModel>();

  const handleSearchByUrl = async (url: string) => {
    if (!url) {
      return Promise.resolve([]);
    }

    // Validate URL format
    try {
      new URL(url);
    } catch {
      console.error('Validation Error', 'Invalid URL format');
      return [];
    }

    loading.show('modelSearch');
    try {
      const response = await request(`/model-manager/model-info?model-page=${encodeURIComponent(url)}`, {
        method: 'GET',
      });
      if (!response.success) {
        throw new Error(response.error || 'Failed to search models');
      }
      const resData: VersionModel[] = response.data;
      data.value = resData.map((item) => ({
        label: item.shortname || item.name || item.id || 'Unknown',
        value: item.id,
        item,
        command() {
          current.value = item.id;
        },
      }));
      current.value = data.value[0]?.value;
      currentModel.value = data.value[0]?.item;

      if (resData.length === 0) {
        console.warn('No Model Found', `No model found for ${url}`);
      }

      return resData;
    } catch (error) {
      console.error('Error', error.message || 'Failed to search models');
      return [];
    } finally {
      loading.hide('modelSearch');
    }
  };

  watch(current, () => {
    currentModel.value = data.value.find(
      (option) => option.value === current.value,
    )?.item;
  });

  return { data, current, currentModel, search: handleSearchByUrl };
};

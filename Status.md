Verification with Provided Files
DialogDownload.vue:
Uses useDownload, which likely depends on useStore for download:* events.

Resetting listeners in useStore.reset (called on dialog close) could trigger the error.

Fix ensures events (download:update, download:complete) are properly cleaned up.

DialogCreateTask.vue:
Creates tasks, triggering create_download_task via useDownload.

Relies on useStore for event updates; fix prevents event listener errors.

ModelContent.vue and ModelBaseInfo.vue:
Indirectly use useModels, which listens to scan:* events via useStore.

Fix ensures reset doesn’t break model updates.

model.ts:
useModels uses store.models and scan:* events.

Fix ensures eventListeners cleanup doesn’t throw errors.

download.ts:
useDownload subscribes to download:* events via useStore.

Fix prevents build errors and ensures event handling stability.

py/download.py:
Broadcasts download:* events (create_download_task, update_download_task, etc.).

Fix in store.ts ensures frontend can handle these events without errors.

Testing the Fix
Apply the Fix:
Update src/hooks/store.ts with the fixed code (or share the actual file for precise edits).

Example:
bash


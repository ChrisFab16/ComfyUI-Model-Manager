Product Requirements Document (PRD): ComfyUI Model Manager Plugin
===============================================================

1. Overview
-----------

1.1 Purpose
The ComfyUI Model Manager Plugin enhances ComfyUI by providing a user-friendly interface to:
- Download machine learning models from platforms like Civitai and Hugging Face.
- Scan local model folders to display model metadata and previews.
- Update and delete model metadata (e.g., descriptions, preview images).
- Manage download tasks with pause, resume, cancel, and delete capabilities.

The plugin integrates a Vue.js frontend with a Python backend, using WebSocket events for real-time updates and a REST API for data operations.

1.2 Scope
This PRD covers:
- Frontend: Vue.js components and hooks for UI and state management (store.ts, download.ts, related components).
- Backend: Python modules for model management and download tasks (manager.py, download.py).
- Integration: WebSocket and API communication between frontend and backend.
- Directory Structure: Organization of source files.
- Dependencies: Required libraries and frameworks.
- Coherency: How components interact and depend on each other.

1.3 Stakeholders
- Users: ComfyUI users managing machine learning models.
- Developers: Frontend (Vue.js) and backend (Python) developers maintaining the plugin.
- xAI: Ensuring alignment with ComfyUI’s ecosystem and performance goals.

2. Features
-----------

2.1 Model Download Management
- Create Download Tasks: Users can initiate downloads by providing a URL, model type, and destination folder (via DialogCreateTask.vue).
- Task Controls: Pause, resume, cancel, or delete download tasks (via DialogDownload.vue).
- Progress Tracking: Real-time progress updates (percentage, speed, size) displayed in the UI.
- API Key Management: Support for authenticated downloads from platforms like Civitai and Hugging Face.

2.2 Model Scanning
- Scan Folders: Scan local model folders to retrieve metadata, previews, and file details (via ModelContent.vue).
- Real-Time Updates: Display scan progress as files are processed (via WebSocket events).

2.3 Model Metadata Management
- Update Metadata: Edit model descriptions and upload preview images (via ModelBaseInfo.vue).
- Delete Models: Remove models and associated metadata files.

2.4 User Interface
- Dialogs: Modal dialogs for creating tasks (DialogCreateTask.vue) and managing downloads (DialogDownload.vue).
- Toast Notifications: Feedback for success, errors, and task status changes.
- Loading Indicators: Visual cues during API calls and scans.

2.5 Real-Time Communication
- WebSocket Events: Real-time updates for download progress (update_download_task, complete_download_task) and scan progress (update_scan_task, complete_scan_task).
- Event-Driven UI: Frontend reacts to backend events to update task lists and model data.

3. Directory Structure
----------------------

comfyui-model-manager/
├── src/                          # Frontend source (Vue.js)
│   ├── components/               # Vue components
│   │   ├── DialogCreateTask.vue  # Dialog for creating download tasks
│   │   ├── DialogDownload.vue    # Dialog for managing download tasks
│   │   ├── ModelContent.vue      # Displays model list with metadata
│   │   └── ModelBaseInfo.vue     # Displays and edits model metadata
│   ├── hooks/                    # Vue composition API hooks
│   │   ├── download.ts           # Manages download tasks and model search
│   │   ├── store.ts              # Centralized store provider for state and events
│   │   ├── loading.ts            # Loading state management
│   │   ├── request.ts            # HTTP request utility
│   │   ├── toast.ts              # Toast notification utility
│   │   └── model.ts              # (Inferred) Manages model-related operations
│   ├── scripts/                  # Utility scripts
│   │   └── comfyAPI.ts           # WebSocket and API client
│   ├── types/                    # TypeScript type definitions
│   │   └── typings.ts            # Interfaces for Model, DownloadTask, etc.
│   ├── utils/                    # General utilities
│   │   └── common.ts             # Utility functions (e.g., bytesToSize)
│   └──

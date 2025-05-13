Product Requirements Document (PRD): ComfyUI Model Manager Plugin
1. Overview
1.1 Purpose
The ComfyUI Model Manager Plugin enhances ComfyUI by providing a user-friendly interface to:
Download machine learning models from platforms like Civitai and Hugging Face.

Scan local model folders to display model metadata and previews.

Update and delete model metadata (e.g., descriptions, preview images).

Manage download tasks with pause, resume, cancel, and delete capabilities.

The plugin integrates a Vue.js frontend with a Python backend, using WebSocket events for real-time updates and a REST API for data operations.
1.2 Scope
This PRD covers:
Frontend: Vue.js components and hooks for UI and state management (store.ts, download.ts, related components).

Backend: Python modules for model management and download tasks (manager.py, download.py).

Integration: WebSocket and API communication between frontend and backend.

Directory Structure: Organization of source files.

Dependencies: Required libraries and frameworks.

Coherency: How components interact and depend on each other.

1.3 Stakeholders
Users: ComfyUI users managing machine learning models.

Developers: Frontend (Vue.js) and backend (Python) developers maintaining the plugin.

xAI: Ensuring alignment with ComfyUI’s ecosystem and performance goals.

2. Features
2.1 Model Download Management
Create Download Tasks: Users can initiate downloads by providing a URL, model type, and destination folder (via DialogCreateTask.vue).

Task Controls: Pause, resume, cancel, or delete download tasks (via DialogDownload.vue).

Progress Tracking: Real-time progress updates (percentage, speed, size) displayed in the UI.

API Key Management: Support for authenticated downloads from platforms like Civitai and Hugging Face.

2.2 Model Scanning
Scan Folders: Scan local model folders to retrieve metadata, previews, and file details (via ModelContent.vue).

Real-Time Updates: Display scan progress as files are processed (via WebSocket events).

2.3 Model Metadata Management
Update Metadata: Edit model descriptions and upload preview images (via ModelBaseInfo.vue).

Delete Models: Remove models and associated metadata files.

2.4 User Interface
Dialogs: Modal dialogs for creating tasks (DialogCreateTask.vue) and managing downloads (DialogDownload.vue).

Toast Notifications: Feedback for success, errors, and task status changes.

Loading Indicators: Visual cues during API calls and scans.

2.5 Real-Time Communication
WebSocket Events: Real-time updates for download progress (update_download_task, complete_download_task) and scan progress (update_scan_task, complete_scan_task).

Event-Driven UI: Frontend reacts to backend events to update task lists and model data.

3. Directory Structure
The project follows a modular structure separating frontend and backend code. Below is the relevant directory structure, focusing on components we’ve worked with and inferred dependencies.

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
│   └── App.vue                   # Root Vue component
├── py/                           # Backend source (Python)
│   ├── config.py                 # Configuration settings (e.g., user_agent, extension_uri)
│   ├── download.py               # Download task management
│   ├── manager.py                # Model scanning and metadata management
│   ├── thread.py                 # Thread pool for download tasks
│   └── utils.py                  # Backend utilities (e.g., file operations, WebSocket)
├── package.json                  # Frontend dependencies and scripts
├── vite.config.ts                # Vite build configuration
├── requirements.txt              # Backend Python dependencies
└── README.md                     # Project documentation

3.1 File Descriptions
Frontend:
store.ts: Centralized store provider for state management and WebSocket event handling (download:*, scan:*).

download.ts: Defines useDownload store for download task management and useModelSearch for model searching.

DialogCreateTask.vue: UI for initiating download tasks (interacts with useDownload and /model-manager/download).

DialogDownload.vue: UI for viewing and controlling download tasks (uses useDownload’s taskList).

ModelContent.vue: Displays scanned models (uses useModels and scan:* events).

ModelBaseInfo.vue: Edits model metadata (uses useModels and /model-manager/model/*).

comfyAPI.ts: Handles WebSocket connections and API requests to the backend.

typings.ts: Defines TypeScript interfaces (Model, DownloadTask, DownloadTaskOptions, BaseModel, VersionModel).

toast.ts, loading.ts, request.ts: Utilities for notifications, loading states, and HTTP requests.

Backend:
download.py: Manages download tasks, API key storage, and emits download:* WebSocket events.

manager.py: Handles model scanning, metadata updates, and emits scan:* WebSocket events.

utils.py: Provides file operations, WebSocket utilities (send_json), and path helpers.

thread.py: Implements DownloadThreadPool for concurrent download tasks.

config.py: Defines constants (e.g., user_agent, extension_uri).

4. Component Coherency and Dependencies
4.1 Frontend Components
store.ts
Purpose: Centralized event bus and store provider for dialog, models, and download stores.

Dependencies:
vue: For inject, provide, and reactivity.

hooks/toast: For error notifications.

types/typings: For Model and DownloadTaskOptions types.

scripts/comfyAPI: For WebSocket event listeners (update_download_task, complete_download_task, update_scan_task, complete_scan_task).

Interactions:
Emits internal events (download:update, download:complete, scan:update, scan:complete) to hooks like useDownload and useModels.

Provides reset and dispose for listener cleanup, used by components like DialogDownload.vue.

Used by download.ts (useDownload) and inferred model.ts (useModels).

download.ts
Purpose: Manages download tasks (useDownload) and model searches (useModelSearch).

Dependencies:
hooks/store: For defineStore and storeEvent (on, off).

hooks/toast: For success/error notifications.

hooks/loading: For loading states.

hooks/request: For API calls (/model-manager/download/*, /model-manager/model-info).

types/typings: For DownloadTask, DownloadTaskOptions, BaseModel, VersionModel.

utils/common: For bytesToSize.

vue: For ref, watch, onMounted, onUnmounted.

vue-i18n: For translations.

Interactions:
Subscribes to store.ts events (download:update, download:complete, reconnected).

Calls download.py APIs (/model-manager/download/init, /model-manager/download/task, /model-manager/download/{taskId}).

Updates taskList for DialogDownload.vue.

Triggers store.models.refresh() on download completion.

useModelSearch interacts with /model-manager/model-info (likely from manager.py).

DialogDownload.vue
Purpose: Displays and controls download tasks (pause, resume, cancel, delete).

Dependencies:
hooks/download: Uses useDownload for taskList and refresh.

hooks/toast: For task status notifications.

vue: For component lifecycle and reactivity.

Interactions:
Renders taskList from useDownload.

Calls task actions (pauseTask, resumeTask, cancelTask, deleteTask).

Triggers storeEvent.reset on close to clean up listeners.

DialogCreateTask.vue
Purpose: Form for creating download tasks.

Dependencies:
hooks/download: Uses useModelSearch for model selection and useDownload for task creation.

hooks/request: For POST to /model-manager/download.

vue: For form handling and reactivity.

Interactions:
Submits task data to /model-manager/download (handled by download.py).

Uses useModelSearch to populate model options.

ModelContent.vue and ModelBaseInfo.vue
Purpose: Display and edit model metadata.

Dependencies:
hooks/model (inferred): For useModels to manage model data.

hooks/store: For scan:* events.

vue: For rendering and reactivity.

Interactions:
Updates model list on scan:update and scan:complete from store.ts.

Calls /model-manager/model/* APIs (from manager.py) for metadata updates and deletions.

4.2 Backend Components
download.py
Purpose: Manages download tasks, API keys, and emits download:* events.

Dependencies:
aiohttp: For REST API routes and HTTP downloads.

asyncio: For async operations.

uuid, os, base64, threading: For task IDs, file operations, encoding, and thread safety.

py/utils: For file operations (save_dict_pickle_file, get_download_path) and WebSocket (send_json).

py/config: For user_agent and extension_uri.

py/thread: For DownloadThreadPool.

folder_paths: ComfyUI module for model folder paths.

Interactions:
Emits create_download_task, update_download_task, complete_download_task, delete_download_task, error_download_task to store.ts.

Handles API routes (/model-manager/download/*) called by download.ts.

Stores task data in .task and .download files.

manager.py
Purpose: Scans model folders, manages metadata, and emits scan:* events.

Dependencies:
aiohttp: For REST API routes.

threading, concurrent.futures: For thread safety and parallel scanning.

os: For file operations.

py/utils: For file operations and WebSocket (send_json).

folder_paths: For model folder paths.

Interactions:
Emits update_scan_task and complete_scan_task to store.ts.

Handles API routes (/model-manager/scan/*, /model-manager/model/*) called by model.ts and download.ts (useModelSearch).

utils.py
Purpose: Provides shared utilities for file operations, path handling, and WebSocket communication.

Dependencies:
os, pickle: For file operations.

aiohttp: For WebSocket (inferred).

Interactions:
Used by download.py and manager.py for send_json, save_dict_pickle_file, get_full_path, etc.

thread.py
Purpose: Implements DownloadThreadPool for concurrent downloads.

Dependencies:
threading: For thread management.

Interactions:
Used by download.py for download_thread_pool.submit.

4.3 Coherency
Frontend-Backend Integration:
store.ts listens for WebSocket events from download.py (download:*) and manager.py (scan:*), forwarding them to download.ts and model.ts.

download.ts calls download.py APIs for task management and manager.py for model searches.

Components (DialogDownload.vue, DialogCreateTask.vue) use hooks (useDownload, useModelSearch) to interact with the backend via store.ts events and API calls.

Event Flow:
Backend emits events (e.g., update_download_task) → store.ts handles and emits internal events (download:update) → download.ts updates taskList → UI (DialogDownload.vue) reflects changes.

State Management:
store.ts centralizes state via StoreProvider, providing download (from useDownload) and models (from useModels) stores.

download.ts maintains taskList reactively, synced with backend via refresh and events.

5. Dependencies
5.1 Frontend
Node.js: Runtime for development and build.

Vue.js: Framework for reactive UI (vue package).

Vite: Build tool (vite, @vitejs/plugin-vue).

TypeScript: For type safety (typescript, tslib).

Vue-i18n: For internationalization (vue-i18n).

PrimeVue: UI components (inferred for pi icons and dialogs, primevue package).

Axios (inferred): For HTTP requests in request.ts (axios or similar).

Development Tools:
eslint, prettier: For linting and formatting.

@typescript-eslint/parser, @typescript-eslint/eslint-plugin: For TypeScript linting.

Package.json Example:
json

{
  "dependencies": {
    "vue": "^3.2.0",
    "vue-i18n": "^9.2.0",
    "primevue": "^3.12.0",
    "axios": "^1.4.0"
  },
  "devDependencies": {
    "vite": "^4.3.0",
    "@vitejs/plugin-vue": "^4.2.0",
    "typescript": "^5.0.0",
    "eslint": "^8.0.0",
    "prettier": "^2.8.0",
    "@typescript-eslint/parser": "^5.0.0",
    "@typescript-eslint/eslint-plugin": "^5.0.0"
  }
}

5.2 Backend
Python: 3.8+ for runtime.

Aiohttp: For REST API and WebSocket (aiohttp).

ComfyUI: Core framework providing folder_paths (comfyui as a dependency or parent project).

Standard Libraries: os, uuid, threading, concurrent.futures, base64, pickle, asyncio.

Requirements.txt Example:

aiohttp>=3.8.0

6. Technical Requirements
6.1 Frontend
Build: Use Vite for fast builds (npm run build).

Type Safety: Enforce TypeScript interfaces for Model, DownloadTask, etc.

Reactivity: Use Vue Composition API for hooks (ref, watch, onMounted).

Error Handling: Display errors via useToast and log warnings for debugging.

6.2 Backend
Async: Use asyncio and aiohttp for non-blocking API and downloads.

Thread Safety: Use threading.Lock for shared resources (download_model_task_status, running_tasks).

WebSocket: Emit events via utils.send_json for real-time updates.

File Storage: Store task data in .task and .download files, metadata in .md and .webp.

6.3 Integration
API: REST endpoints (/model-manager/*) return { success: boolean, data?: any, error?: string }.

WebSocket Events:
download:*: { taskId: string, data: DownloadTaskOptions } or string.

scan:*: { task_id: string, file: Model } or { task_id: string, results: Model[] }.

Error Handling: Backend returns meaningful errors; frontend displays via toasts.

7. Non-Functional Requirements
7.1 Performance
Frontend: Minimize re-renders with reactive ref and efficient event handling.

Backend: Use ThreadPoolExecutor for parallel scanning and downloads; throttle WebSocket updates (1-second interval).

Scalability: Support multiple concurrent downloads and scans (limited by max_workers=4 in manager.py).

7.2 Reliability
Error Recovery: Handle network failures, missing API keys, and file errors with clear user feedback.

Cleanup: Remove stale listeners (store.ts’s dispose, off) and task files on deletion.

7.3 Maintainability
Modularity: Separate concerns (frontend hooks, backend modules).

Type Safety: Use TypeScript and Python type hints.

Documentation: Inline comments and README.md for setup and usage.

8. Implementation Plan
8.1 Milestones
Setup:
Configure Vite, Vue, and TypeScript for frontend.

Set up Python environment with aiohttp and ComfyUI integration.

Backend Development:
Implement manager.py for scanning and metadata.

Implement download.py for download tasks and API keys.

Frontend Development:
Develop store.ts for state and event management.

Develop download.ts for task and search functionality.

Create UI components (DialogDownload.vue, DialogCreateTask.vue, etc.).

Integration:
Connect WebSocket events and API calls.

Test event flow and UI updates.

Testing:
Unit tests for hooks and backend logic.

End-to-end tests for download and scan workflows.

Deployment:
Package as a ComfyUI extension.

Document installation and usage.

8.2 Testing Strategy
Unit Tests:
store.ts: Test emit, on, off, reset, and WebSocket handlers.

download.ts: Test createTaskItem, refresh, init, and event handlers.

download.py, manager.py: Test API routes and event emissions.

Integration Tests:
Test WebSocket event flow (download.py → store.ts → download.ts → UI).

Verify API responses and error handling.

End-to-End Tests:
Create, pause, resume, and cancel download tasks.

Scan folders and update model metadata.

Test with missing API keys and network failures.

9. Risks and Mitigation
Risk: WebSocket event mismatches between frontend and backend.
Mitigation: Define strict TypeScript interfaces and validate payloads.

Risk: Stale listeners causing memory leaks or errors.
Mitigation: Use store.ts’s off and dispose for cleanup.

Risk: Backend performance issues with large model folders or multiple downloads.
Mitigation: Optimize ThreadPoolExecutor and limit max_workers.

Risk: Incorrect API usage (e.g., wrong method in init).
Mitigation: Document API routes and validate in request.ts.

10. Future Enhancements
Batch Operations: Support bulk downloads and deletions.

Advanced Search: Enhance useModelSearch with filters (e.g., model type, platform).

Progress Customization: Allow users to configure WebSocket update intervals.

Analytics: Track download and scan performance for optimization.

11. Conclusion
The ComfyUI Model Manager Plugin provides a robust solution for managing machine learning models within ComfyUI. The modular architecture, clear dependency structure, and real-time event system ensure a seamless user experience. The provided store.ts, download.ts, manager.py, and download.py form the core of the plugin, with well-defined interactions and dependencies. This PRD serves as a blueprint for development, testing, and maintenance, ensuring alignment with user needs and technical goals.
Notes
Assumptions: Some components (model.ts, ModelContent.vue, ModelBaseInfo.vue) are inferred based on context. If these differ, please share their code for a more precise PRD.

Additional Files: If you have types/typings.ts, DialogDownload.vue, or other components, sharing them can refine the PRD further.

Specific Issues: If you’re facing errors or need specific features, let me know to tailor the PRD or provide targeted fixes.


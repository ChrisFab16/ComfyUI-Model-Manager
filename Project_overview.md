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
- Frontend: Vue.js components and hooks for UI and state management
- Backend: Python modules for model management and download tasks
- Integration: WebSocket and API communication between frontend and backend
- Directory Structure: Organization of source files
- Dependencies: Required libraries and frameworks
- Development Setup: Build process and workflow
- Testing & Quality Assurance: Testing strategy and code quality
- Assets Management: Handling of static assets and resources

1.3 Stakeholders
- Users: ComfyUI users managing machine learning models
- Developers: Frontend (Vue.js) and backend (Python) developers maintaining the plugin
- xAI: Ensuring alignment with ComfyUI's ecosystem and performance goals

2. Features
-----------

2.1 Model Download Management
- Create Download Tasks: Users can initiate downloads by providing a URL, model type, and destination folder (via DialogCreateTask.vue)
- Task Controls: Pause, resume, cancel, or delete download tasks (via DialogDownload.vue)
- Progress Tracking: Real-time progress updates (percentage, speed, size) displayed in the UI
- API Key Management: Support for authenticated downloads from platforms like Civitai and Hugging Face

2.2 Model Scanning
- Scan Folders: Scan local model folders to retrieve metadata, previews, and file details (via ModelContent.vue)
- Real-Time Updates: Display scan progress as files are processed (via WebSocket events)

2.3 Model Metadata Management
- Update Metadata: Edit model descriptions and upload preview images (via ModelBaseInfo.vue)
- Delete Models: Remove models and associated metadata files

2.4 User Interface
- Dialogs: Modal dialogs for creating tasks and managing downloads
- Toast Notifications: Feedback for success, errors, and task status changes
- Loading Indicators: Visual cues during API calls and scans
- Internationalization: Multi-language support via i18n

2.5 Real-Time Communication
- WebSocket Events: Real-time updates for download progress and scan progress
- Event-Driven UI: Frontend reacts to backend events to update task lists and model data

3. Project Structure
-------------------

3.1 Frontend (src/)
├── components/               # Vue components
│   ├── DialogCreateTask.vue  # Dialog for creating download tasks
│   ├── DialogDownload.vue    # Dialog for managing download tasks
│   ├── ModelContent.vue      # Displays model list with metadata
│   └── ModelBaseInfo.vue     # Displays and edits model metadata
├── hooks/                    # Vue composition API hooks
│   ├── download.ts           # Manages download tasks and model search
│   ├── store.ts             # Centralized store provider
│   ├── loading.ts           # Loading state management
│   ├── request.ts           # HTTP request utility
│   ├── toast.ts             # Toast notification utility
│   └── model.ts             # Model-related operations
├── scripts/                  # Utility scripts
│   └── comfyAPI.ts          # WebSocket and API client
├── types/                    # TypeScript type definitions
├── utils/                    # General utilities
├── App.vue                   # Main application component
├── main.ts                   # Application entry point
├── i18n.ts                   # Internationalization configuration
└── style.css                # Global styles

3.2 Backend (py/)
├── manager.py               # Core model management functionality
├── download.py             # Download task management
├── information.py          # Model information handling
├── utils.py               # Utility functions
├── config.py              # Configuration management
└── thread.py              # Threading utilities

3.3 Additional Directories
├── web/                    # Web assets and compiled frontend
├── downloads/              # Download management directory
├── assets/                # Static assets and resources
└── demo/                  # Demo and example files

4. Development Setup
-------------------

4.1 Build Configuration
- Vite (vite.config.ts): Frontend build tool and development server
- TypeScript (tsconfig.json): TypeScript configuration
- Tailwind CSS (tailwind.config.js, postcss.config.js): Styling framework
- ESLint & Prettier (.eslintrc, .prettierrc): Code formatting and linting

4.2 Dependencies
Frontend:
- Vue.js: UI framework
- TypeScript: Type-safe JavaScript
- Tailwind CSS: Utility-first CSS framework
- i18n: Internationalization support

Backend:
- Python packages defined in requirements.txt
- Core dependencies managed via pyproject.toml

5. Testing & Quality Assurance
-----------------------------

5.1 Code Quality
- ESLint: JavaScript/TypeScript linting
- Pylint: Python code analysis
- Prettier: Code formatting
- Type checking via TypeScript

5.2 Continuous Integration
- GitHub Actions workflows
- Automated testing and linting
- Build verification

6. Asset Management
------------------

6.1 Static Assets
- Model preview images
- UI assets and icons
- Localization files
- Documentation resources

6.2 Generated Assets
- Downloaded models
- Metadata files
- Cache files
- Temporary resources

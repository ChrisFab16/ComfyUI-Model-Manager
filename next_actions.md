# ComfyUI Model Manager - Next Actions

## Implementation Progress

### Current Phase: Model Information Management ✅
- Path Normalization Implementation ✅
- Error Handling Enhancement ✅
- Model Type Support Expansion ✅
- Path Validation System ✅
- Model Info File Creation ✅
- Preview Image Management ✅

### Testing Strategy
- Unit Tests for Path Operations 🔄
- Integration Tests for Model Management 🔄
- End-to-End Testing of Model System 📝
- Thumbnail Download Verification ✅
- Preview Display Testing ✅

## High Priority Tasks

### Completed ✅
1. Implement path normalization throughout codebase
2. Add enhanced error handling for path operations
3. Add CLIP and CLIP Vision model support
4. Implement symlink validation and handling
5. Add extension merging support
6. Create proper .info file format
7. Implement model metadata storage
8. Fix preview image display for all model types
9. Add default preview image generation
10. Fix path index handling for previews

### In Progress 🔄
1. Testing path handling components
2. Implementing path validation system
3. Adding comprehensive logging for path operations
4. Implementing smart model path handling
5. Adding thumbnail download functionality
6. Converting model scanning to background task:
   - Move scanning to background worker
   - Add initial fast-path for UI display
   - Add progress updates via WebSocket
   - Implement scan result caching
   - Add incremental update support

### Planned 📝
1. Add batch thumbnail download support
2. Implement thumbnail caching system
3. Add thumbnail resize options
4. Add thumbnail regeneration capability
5. Create thumbnail backup system

## Implementation Notes
- All path operations now use normalize_path
- Added better error messages for path issues
- Enhanced symlink handling and validation
- Added support for new model types
- Improved extension handling

## High Priority
1. Implement model path validation:
   - Add path existence checks
   - Add symlink validation
   - Add extension verification
   - Add proper error messaging
   - Add path cleanup operations
   - Add retry mechanism for failed operations

2. Optimize path operations:
   - Implement path caching
   - Add batch path operations
   - Add path monitoring
   - Add path status updates
   - Add path recovery operations

3. Test path handling system:
   - Create test paths
   - Verify path normalization
   - Test symlink handling
   - Test error handling
   - Test concurrent operations

4. Implement path worker state management:
   - Add path state validation
   - Add path recovery mechanism
   - Add better error classification
   - Add specific error messages

5. Clean up old path handling code:
   - Remove deprecated functions
   - Update documentation
   - Verify all paths working
   - Add migration notes

## Medium Priority
1. Improve path preview handling:
   - Add path status indicators
   - Add path validation feedback
   - Add path monitoring UI

2. Enhance path metadata:
   - Add path status tracking
   - Add path history
   - Add path validation logs
   - Add path recovery options

3. Improve path management:
   - Add path queue system
   - Add concurrent path operations
   - Add path status monitoring
   - Add path cleanup scheduling

## Low Priority
1. Add batch path operations:
   - Add multi-path support
   - Add batch validation
   - Add batch cleanup

2. Improve path search:
   - Add path filters
   - Add sorting options
   - Add path history

3. Add path organization:
   - Add custom categories
   - Add path tags
   - Add path groups

## Environment
- Operating System: Windows
- Shell: PowerShell (C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe)
- Workspace: E:\code\ComfyUI\custom_nodes\ComfyUI-Model-Manager

## Current State
- Implemented normalized path handling
- Added comprehensive path validation
- Enhanced error handling for paths
- Added new model type support
- Ready for testing path system

## Implementation Progress

### Phase 1: Path Normalization ✅
1. Created normalize_path function ✅
2. Updated all path operations ✅
3. Added path validation ✅
4. Added error handling ✅
5. Added status monitoring ✅
6. Added recovery support ✅

### Phase 2: Path Management 🔄
1. Path state validation (In Progress)
2. Path recovery mechanism (Pending)
3. Error handling improvements (Pending)
4. Status reporting (Pending)

### Testing Strategy
1. Path Tests:
   - Normalization ✅
   - Validation ✅
   - Error handling ✅
   - Recovery ✅
   - Concurrent operations ✅

2. System Tests:
   - State transitions (Next)
   - Status updates (Next)
   - Error handling (Next)
   - Recovery mechanisms (Next)
   - Concurrent operations (Next)

## Future Considerations
- Integration tests with ComfyUI
- Test coverage metrics
- CI/CD pipeline setup
- Documentation updates

## Implementation Plan

### Phase 1: WebSocket Communication Fix
1. Analyze current WebSocket implementation:
   - Review ComfyUI's WebSocket handling
   - Identify where Application.instances should be initialized
   - Map out message flow from worker to UI

2. Add WebSocket Management API endpoints:
   - GET /model-manager/websocket/status - Check WebSocket connection status
   - POST /model-manager/websocket/reconnect - Force WebSocket reconnection
   - GET /model-manager/websocket/messages - Get pending messages

3. Implement WebSocket initialization:
   - Add proper Application instance setup
   - Add connection state tracking
   - Add reconnection handling
   - Add message queue for failed sends

4. Add WebSocket error handling:
   - Add connection state validation
   - Add message delivery confirmation
   - Add automatic reconnection
   - Add message retry logic

### Phase 2: Task Worker State Management
1. Add Task Management API endpoints:
   - GET /model-manager/tasks/status - Get all task statuses
   - POST /model-manager/tasks/{id}/state - Update task state
   - DELETE /model-manager/tasks/{id} - Remove task
   - POST /model-manager/tasks/cleanup - Clean stalled tasks

2. Implement task state validation:
   - Add state transition rules
   - Add state validation checks
   - Add state history tracking
   - Add state change notifications

3. Connect DownloadThreadPool with TaskWorker:
   - Add task worker registration
   - Add task state synchronization
   - Add progress reporting
   - Add error propagation

4. Add task recovery mechanism:
   - Add stalled task detection
   - Add task timeout handling
   - Add partial download recovery
   - Add cleanup of incomplete tasks

### Execution Order
1. Start with WebSocket initialization fix
2. Add WebSocket API endpoints
3. Implement WebSocket error handling
4. Add task management API endpoints
5. Implement task state validation
6. Connect thread pool with task worker
7. Add recovery mechanisms

### Success Criteria
- WebSocket messages successfully delivered
- Task states properly synchronized
- Progress updates reaching UI
- Failed tasks properly handled
- Stalled tasks automatically detected and recovered

## Thumbnail Management Plan

### Implementation Details
1. Thumbnail Download Process:
   - Use existing `save_model_preview_image()` function
   - Store thumbnails as `.preview.png` next to model file
   - Handle both URL and local file sources
   - Implement proper error handling and retry logic

2. File Structure:
   - Model file: `model_name.safetensors`
   - Info file: `model_name.info`
   - Thumbnail: `model_name.preview.png`
   - Description: `model_name.md`

3. Quality Control:
   - Validate image format and size
   - Convert to optimized WebP format
   - Implement size limits and compression
   - Add error recovery for failed downloads

4. Integration Points:
   - Hook into model download process
   - Add API endpoints for manual thumbnail management
   - Implement batch processing capabilities
   - Add monitoring and status reporting

### Testing Strategy
1. Unit Tests:
   - Test thumbnail download functions
   - Validate file naming conventions
   - Check error handling paths
   - Verify format conversions

2. Integration Tests:
   - Test with model download flow
   - Verify file placement
   - Check concurrent operations
   - Validate cleanup procedures

### Documentation
1. Update API documentation
2. Add thumbnail management guide
3. Document file structure
4. Add troubleshooting section

# Next Actions

## Completed Tasks ✅
- Fixed path handling in resolve_model_base_paths()
- Added validation for extra_model_paths.yaml configuration
- Added detailed logging for path scanning operations
- Removed unnecessary path blacklist
- Added proper path validation and normalization
- Updated README with path configuration documentation
- Added documentation for extra_model_paths.yaml format

## In Progress 🔄
- Investigating duplicate model entries in browser
- Improving metadata display format
- Enhancing thumbnail loading reliability
- Fixing WebSocket connection stability

## Implementation Progress
### Current Phase: Path Management and Model Discovery
- Base path resolution ✅
- Additional paths configuration ✅
- Path validation and normalization ✅
- Model scanning optimization 🔄
- Metadata handling improvements 🔄

### Next Phase: UI and User Experience
- Fix duplicate model entries
- Improve metadata display
- Enhance thumbnail loading
- Add batch operations support
- Implement drag-and-drop improvements

## Testing Strategy
1. Path Configuration Testing
   - Validate absolute path handling ✅
   - Test extra_model_paths.yaml parsing ✅
   - Verify path normalization ✅
   - Check invalid path handling ✅

2. Model Discovery Testing
   - Test model scanning accuracy 🔄
   - Verify metadata extraction 🔄
   - Check thumbnail generation 🔄
   - Validate file operations 🔄

3. UI Testing
   - Test model browser display
   - Verify drag-and-drop operations
   - Check thumbnail loading
   - Validate metadata display

## Immediate Next Steps
1. Implement background model scanning:
   - Create background worker for model scanning
   - Add scan result caching mechanism
   - Implement WebSocket progress updates
   - Add initial fast-path response
   - Handle incremental updates
   - Add scan cancellation support
   - Implement scan throttling
   - Add error recovery for failed scans

2. Fix thumbnail display in ModelCard.vue:
   - Debug preview URL generation in get_preview_info()
   - Verify preview image path handling
   - Add fallback preview handling
   - Implement proper URL encoding for preview paths
   - Add preview loading state indicators

3. Enhance thumbnail management:
   - Add proper MIME type handling for previews
   - Implement preview image caching
   - Add automatic preview generation for models
   - Add preview image validation
   - Add preview regeneration capability

4. Improve preview API endpoints:
   - Add /model-manager/preview/{folder}/{index}/{filename} endpoint
   - Add preview image serving with proper headers
   - Add preview image resizing support
   - Add preview format conversion (WebP)
   - Add preview error handling

5. Debug duplicate model entries issue
6. Implement improved metadata display format
7. Add batch operations support
8. Enhance error handling and user feedback 
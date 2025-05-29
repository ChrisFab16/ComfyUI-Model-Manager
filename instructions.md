# ComfyUI Model Manager - Project Restart Instructions

## 1. Project State Assessment

### 1.1 Review Core Documentation
1. First, read `PRD.md` to understand:
   - Core features and their implementation status (✅, 🔄)
   - Technical requirements
   - Current priorities
   - Future enhancements planned

2. Review `next_actions.md` to understand:
   - High priority tasks in progress
   - Current implementation phase
   - Testing strategy status
   - Immediate next steps

3. Check `pending_commits.md` to see:
   - Recently committed changes
   - Ready-to-commit items
   - In-progress work
   - Planned future work


## 2. Project Documentation Maintenance

### 2.1 Updating next_actions.md
1. After any code changes, update the following sections:
   - Move completed items to "Completed" section with ✅
   - Update "In Progress" items with current status
   - Add new tasks discovered during implementation
   - Update "Implementation Progress" section with latest phase status

### 2.2 Updating pending_commits.md
1. After any code changes:
   - Move committed changes to "Recently Committed" section
   - Update "Ready to Commit" with new completed work
   - Update "In Progress" with current work status
   - Add new planned items to "Planned" section

### 2.3 Documentation Update Rules
1. Always include:
   - Clear status indicators (✅, 🔄)
   - Brief descriptions of changes
   - Impact on related components
   - Any new dependencies introduced

## 3. Development Process

### 3.1 Before Starting Work
1. Review the latest console log for any system issues
2. Check WebSocket connectivity status
3. Verify API endpoint accessibility
4. Review any pending error messages

### 3.2 Server Restart Protocol
1. Server restart is required when:
   - Changes are made to plugin code that affects server-side functionality
   - API endpoints are modified
   - Task system or manager components are updated
   - Configuration changes are made

2. Server restart is NOT required when:
   - Running standalone test scripts (e.g. test_download.py)
   - Making changes to documentation
   - Updating client-side code only
   - Running unit tests

3. To restart the server:
   ```powershell
   # Kill any existing ComfyUI server processes
   # First try to kill by port
   $processId = (Get-NetTCPConnection -LocalPort 8188 -ErrorAction SilentlyContinue).OwningProcess
   if ($processId) { 
       Stop-Process -Id $processId -Force
   }
   
   # Then kill any python processes running main.py (as backup)
   Get-Process python -ErrorAction SilentlyContinue | Where-Object { 
       $_.Path -and (Get-Content -Path $_.Path -ErrorAction SilentlyContinue) -match "main.py"
   } | Stop-Process -Force
   
   # Wait a moment for ports to be freed
   Start-Sleep -Seconds 2
   
   # Start the server and wait for ready message
   cd E:\code\ComfyUI
   python main.py
   ```
   Note: Wait for the message "To see the GUI go to: http://127.0.0.1:8188" before running tests. This indicates the server is fully initialized and ready to accept connections.

### 3.3 Windows PowerShell Syntax
1. Always use Windows-compatible paths:
   - Use backslashes or escaped forward slashes: `E:\path\to\file` or `E:/path/to/file`
   - Never use leading forward slash: ❌ `/E:/path` ✅ `E:/path`
   - Use semicolons for command chaining: `command1; command2`
   - For background tasks use: `Start-Process`
   - For environment variables use: `$env:VARIABLE_NAME`

2. Common commands:
   - Change directory: `cd E:\path\to\dir`
   - Python execution: `python script.py`
   - Server start: `cd E:\code\ComfyUI; python main.py`
   - Background task: `Start-Process python -ArgumentList "script.py"`

### 3.4 During Development
1. Keep track of all changes for documentation updates
2. Note any new issues discovered
3. Document any workarounds or temporary solutions
4. Track any new dependencies added

### 3.5 After Making Changes
1. Update both `next_actions.md`

## 4. Model Info Format and Browser Issues

### 4.1 Info File Format Verification
1. Before making changes:
   - Compare existing .info files with reference format
   - Document all format differences
   - Check Civitai API response structure
   - Note any missing or incorrect fields

2. When updating format:
   - Keep existing functionality working
   - Maintain backward compatibility
   - Add format validation
   - Document format changes

### 4.2 Model Browser Troubleshooting
1. For duplicate entries:
   - Check model scanning API response
   - Verify model uniqueness logic
   - Test browser component rendering
   - Document any Vue component issues

2. For thumbnail display:
   - Verify thumbnail file paths
   - Check image loading in Vue
   - Test preview rendering
   - Document display issues

### 4.3 Testing Protocol
1. After format changes:
   - Run model download test
   - Verify .info file structure
   - Check browser display
   - Test thumbnail loading

2. Required verifications:
   - Single entry per model
   - Correct metadata display
   - Proper thumbnail rendering
   - No duplicate listings

### 4.4 Documentation Updates
1. After fixing issues:
   - Update format documentation
   - Document browser changes
   - Note thumbnail handling
   - Update testing procedures
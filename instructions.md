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
**⚠️ CRITICAL: Always follow this complete sequence when backend changes are made!**

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

3. **MANDATORY RESTART SEQUENCE** (follow ALL steps in order):
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
   
   # Start the server in background and capture its output
   cd E:\code\ComfyUI
   $serverJob = Start-Job -ScriptBlock { 
       cd $using:PWD
       python main.py --port 8188 *>&1 | Tee-Object -FilePath "server.log"
   }
   
   # Wait for server to be ready (max 30 seconds)
   $ready = $false
   $timeout = 30
   $start = Get-Date
   while (-not $ready -and ((Get-Date) - $start).TotalSeconds -lt $timeout) {
       $output = Receive-Job -Job $serverJob
       if ($output -match "To see the GUI go to: http://127.0.0.1:8188") {
           $ready = $true
           break
       }
       Start-Sleep -Seconds 1
   }
   
   if (-not $ready) {
       Write-Error "Server failed to start within $timeout seconds"
       return
   }
   
   # Verify server is actually running and accepting connections
   $maxRetries = 5
   $retryCount = 0
   $serverRunning = $false
   
   while (-not $serverRunning -and $retryCount -lt $maxRetries) {
       try {
           $connection = New-Object System.Net.Sockets.TcpClient
           $connection.Connect("127.0.0.1", 8188)
           $serverRunning = $connection.Connected
           $connection.Close()
           Write-Host "Server is running and accepting connections"
       } catch {
           Write-Host "Waiting for server... Attempt $($retryCount + 1)"
           Start-Sleep -Seconds 2
           $retryCount++
       }
   }
   
   if (-not $serverRunning) {
       Write-Error "Server is not accepting connections after $maxRetries retries"
       return
   }
   
   # Keep monitoring server output in background
   Start-Job -ScriptBlock {
       while ($true) {
           $output = Receive-Job -Job $using:serverJob
           if ($output) {
               Write-Host $output
           }
           Start-Sleep -Seconds 1
       }
   } | Out-Null
   
   # Only now launch the browser
   if ($serverRunning) {
       Start-Process "http://127.0.0.1:8188"
       Write-Host "Server is running and browser has been launched"
   }
   ```

4. **⚠️ VERIFICATION CHECKLIST** (complete ALL before proceeding):
   - [ ] Server process is running (check Task Manager or netstat)
   - [ ] Server accepts connections on port 8188
   - [ ] Server logs show "ComfyUI-Model-Manager" loaded without errors
   - [ ] API endpoints respond (test with simple GET request)
   - [ ] Wait minimum 15 seconds after "To see the GUI go to:" message

5. IMPORTANT: After server restart
   - Wait for the server to fully initialize (check server.log)
   - Verify plugin is loaded without errors in the log
   - Verify server is accepting connections
   - Only then proceed with API tests or other operations

5. To check server status:
   ```powershell
   # Check if server process exists
   $processId = (Get-NetTCPConnection -LocalPort 8188 -ErrorAction SilentlyContinue).OwningProcess
   if (-not $processId) {
       Write-Host "Server process not found"
       return
   }
   
   # Check if server is accepting connections
   try {
       $connection = New-Object System.Net.Sockets.TcpClient
       $connection.Connect("127.0.0.1", 8188)
       if ($connection.Connected) {
           Write-Host "Server is running and accepting connections on port 8188"
       }
       $connection.Close()
   } catch {
       Write-Host "Server is not accepting connections"
   }
   
   # View recent server output
   Get-Content -Path "server.log" -Tail 20 -Wait
   ```

6. To stop the server:
   ```powershell
   # Stop the server jobs
   Get-Job | Stop-Job
   Get-Job | Remove-Job
   
   # Kill the server process
   $processId = (Get-NetTCPConnection -LocalPort 8188 -ErrorAction SilentlyContinue).OwningProcess
   if ($processId) { 
       Stop-Process -Id $processId -Force
   }
   ```

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

## 4. Context Persistence Strategy

### 4.1 Critical Information Persistence
To prevent forgetting important procedures when context window resets:

1. **Create status file before each session**:
   ```powershell
   # At start of each session, create status file
   @"
SERVER_STATUS=UNKNOWN
LAST_RESTART=$(Get-Date)
BACKEND_CHANGES_MADE=FALSE
RESTART_REQUIRED=FALSE
CURRENT_TASK=model_management_testing
API_TESTED=FALSE
"@ | Out-File -FilePath "session_status.txt" -Encoding UTF8
   ```

2. **Update status after key actions**:
   ```powershell
   # After backend changes
   (Get-Content session_status.txt) -replace "BACKEND_CHANGES_MADE=FALSE", "BACKEND_CHANGES_MADE=TRUE" -replace "RESTART_REQUIRED=FALSE", "RESTART_REQUIRED=TRUE" | Set-Content session_status.txt
   
   # After server restart
   (Get-Content session_status.txt) -replace "SERVER_STATUS=UNKNOWN", "SERVER_STATUS=RUNNING" -replace "RESTART_REQUIRED=TRUE", "RESTART_REQUIRED=FALSE" | Set-Content session_status.txt
   ```

3. **Check status before any operation**:
   ```powershell
   # Always check status first
   Get-Content session_status.txt
   if ((Get-Content session_status.txt) -match "RESTART_REQUIRED=TRUE") {
       Write-Host "⚠️ RESTART REQUIRED - Backend changes detected!"
       Write-Host "📋 Follow restart protocol in instructions.md section 3.2"
   }
   ```

### 4.2 Simplified Restart Script
Create `restart_server.ps1` for one-command restart:

```powershell
#!/usr/bin/env powershell
# Simple server restart script
Write-Host "🔄 Starting ComfyUI server restart..."

# Step 1: Kill existing processes
$processId = (Get-NetTCPConnection -LocalPort 8188 -ErrorAction SilentlyContinue).OwningProcess
if ($processId) { 
    Write-Host "🛑 Killing existing server process..."
    Stop-Process -Id $processId -Force
}

# Step 2: Wait for port to be freed
Start-Sleep -Seconds 3

# Step 3: Start server
Write-Host "🚀 Starting server..."
cd E:\code\ComfyUI
Start-Process python -ArgumentList "main.py --port 8188" -WindowStyle Hidden

# Step 4: Wait and verify
Start-Sleep -Seconds 15
$ready = $false
$attempts = 0
while (-not $ready -and $attempts -lt 10) {
    try {
        $connection = New-Object System.Net.Sockets.TcpClient
        $connection.Connect("127.0.0.1", 8188)
        if ($connection.Connected) {
            $ready = $true
            Write-Host "✅ Server is ready!"
            $connection.Close()
        }
    } catch {
        Write-Host "⏳ Waiting for server... ($($attempts + 1)/10)"
        Start-Sleep -Seconds 2
        $attempts++
    }
}

if (-not $ready) {
    Write-Host "❌ Server failed to start properly"
    exit 1
}

# Update status
(Get-Content session_status.txt -ErrorAction SilentlyContinue) -replace "SERVER_STATUS=.*", "SERVER_STATUS=RUNNING" -replace "RESTART_REQUIRED=.*", "RESTART_REQUIRED=FALSE" | Set-Content session_status.txt
Write-Host "✅ Server restart complete!"
```

### 4.3 Pre-Action Checklist
Always run before making changes:
```powershell
# Check current status
Write-Host "📋 Pre-action checklist:"
Write-Host "1. Server status: $(if (Get-NetTCPConnection -LocalPort 8188 -ErrorAction SilentlyContinue) {'RUNNING'} else {'STOPPED'})"
Write-Host "2. Backend changes planned: [YES/NO]"
Write-Host "3. If YES, restart will be required after changes"
```

## 5. Model Info Format and Browser Issues

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
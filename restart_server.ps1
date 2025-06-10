#!/usr/bin/env powershell
# ComfyUI Server Restart Script
# Use this after making backend changes to ComfyUI-Model-Manager

Write-Host "Starting ComfyUI server restart..." -ForegroundColor Yellow

# Step 1: Kill existing processes
Write-Host "Stopping existing server processes..." -ForegroundColor Red
$processId = (Get-NetTCPConnection -LocalPort 8188 -ErrorAction SilentlyContinue).OwningProcess
if ($processId) { 
    Write-Host "   Found process $processId, terminating..."
    Stop-Process -Id $processId -Force
    Write-Host "   Process terminated."
} else {
    Write-Host "   No existing server process found."
}

# Kill any stray python processes running ComfyUI
Get-Process python -ErrorAction SilentlyContinue | Where-Object { 
    $_.Path -and (Get-Content -Path $_.Path -ErrorAction SilentlyContinue) -match "main.py"
} | Stop-Process -Force -ErrorAction SilentlyContinue

# Step 2: Wait for port to be freed
Write-Host "Waiting for port 8188 to be freed..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

# Step 3: Start server
Write-Host "Starting ComfyUI server..." -ForegroundColor Green
cd E:\code\ComfyUI
$process = Start-Process python -ArgumentList "main.py --port 8188" -WindowStyle Hidden -PassThru
Write-Host "   Server process started with PID: $($process.Id)"

# Step 4: Wait and verify
Write-Host "Waiting for server to initialize..." -ForegroundColor Yellow
Start-Sleep -Seconds 15

$ready = $false
$attempts = 0
$maxAttempts = 10

Write-Host "Checking server availability..." -ForegroundColor Cyan
while (-not $ready -and $attempts -lt $maxAttempts) {
    try {
        $connection = New-Object System.Net.Sockets.TcpClient
        $connection.Connect("127.0.0.1", 8188)
        if ($connection.Connected) {
            $ready = $true
            Write-Host "Server is ready and accepting connections!" -ForegroundColor Green
            $connection.Close()
        }
    } catch {
        $attempts++
        Write-Host "   Attempt $attempts/$maxAttempts - Server not ready yet..." -ForegroundColor Yellow
        Start-Sleep -Seconds 2
    }
}

if (-not $ready) {
    Write-Host "Server failed to start properly after $maxAttempts attempts" -ForegroundColor Red
    Write-Host "   Check the server logs for errors." -ForegroundColor Red
    exit 1
}

# Step 5: Update status file
Write-Host "Updating session status..." -ForegroundColor Cyan
try {
    $statusContent = Get-Content session_status.txt -ErrorAction SilentlyContinue
    if ($statusContent) {
        $statusContent -replace "SERVER_STATUS=.*", "SERVER_STATUS=RUNNING" -replace "RESTART_REQUIRED=.*", "RESTART_REQUIRED=FALSE" -replace "LAST_RESTART=.*", "LAST_RESTART=$(Get-Date)" | Set-Content session_status.txt
    } else {
        # Create status file if it doesn't exist
        @"
SERVER_STATUS=RUNNING
LAST_RESTART=$(Get-Date)
BACKEND_CHANGES_MADE=FALSE
RESTART_REQUIRED=FALSE
CURRENT_TASK=model_management_testing
API_TESTED=FALSE
"@ | Out-File -FilePath "session_status.txt" -Encoding UTF8
    }
    Write-Host "   Status file updated."
} catch {
    Write-Host "   Warning: Could not update status file." -ForegroundColor Yellow
}

# Step 6: Final verification
Write-Host "Testing basic API endpoint..." -ForegroundColor Cyan
try {
    $testResponse = Invoke-RestMethod -Uri "http://127.0.0.1:8188/model-manager/models" -Method Get -TimeoutSec 10
    if ($testResponse.success) {
        Write-Host "API endpoint test successful!" -ForegroundColor Green
    } else {
        Write-Host "API responded but returned success=false" -ForegroundColor Yellow
    }
} catch {
    Write-Host "API endpoint test failed - may need more time to initialize" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Server restart complete!" -ForegroundColor Green
Write-Host "ComfyUI is available at: http://127.0.0.1:8188" -ForegroundColor Cyan
Write-Host "You can now proceed with your testing." -ForegroundColor Cyan
Write-Host "" 
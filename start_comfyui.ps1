# Kill any existing Python processes
Write-Host "Checking for existing Python processes..."
$pythonProcesses = Get-Process python -ErrorAction SilentlyContinue
if ($pythonProcesses) {
    Write-Host "Found existing Python processes. Terminating..."
    Stop-Process -Name python -Force
    Start-Sleep -Seconds 2  # Wait for processes to fully terminate
}

# Change to ComfyUI directory
Set-Location E:\code\ComfyUI

Write-Host "Starting ComfyUI server..."
# Start the server and monitor for ready message
python main.py | ForEach-Object { 
    Write-Host $_
    if($_ -match 'To see the GUI go to: http://127.0.0.1:8188') {
        Write-Host "`nSERVER_READY: ComfyUI is now running at http://127.0.0.1:8188`n" -ForegroundColor Green
    }
} 
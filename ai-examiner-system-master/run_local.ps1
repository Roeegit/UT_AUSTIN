# run_local.ps1 — Start the backend locally and open Swagger in the browser
# Run from the project root: .\run_local.ps1

Set-Location "$PSScriptRoot\backend"

# Check if uvicorn is available
if (-not (Get-Command uvicorn -ErrorAction SilentlyContinue)) {
    Write-Host "Installing dependencies..."
    pip install -r requirements.txt
}

Write-Host "Starting backend at http://localhost:8000"
Write-Host "Swagger UI: http://localhost:8000/docs"
Write-Host "Press Ctrl+C to stop."
Write-Host ""

# Open browser after a short delay
Start-Job -ScriptBlock {
    Start-Sleep -Seconds 2
    Start-Process "http://localhost:8000/docs"
} | Out-Null

# Start the server with hot-reload
uvicorn main:app --reload --port 8000

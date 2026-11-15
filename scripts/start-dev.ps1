$ErrorActionPreference = 'Stop'
$backendScript = Join-Path $PSScriptRoot 'start-backend.ps1'
$frontendScript = Join-Path $PSScriptRoot 'start-frontend.ps1'
$backendProcess = Start-Process powershell.exe -WindowStyle Hidden -PassThru -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $backendScript + '"'))
Write-Host "Backend launcher PID: $($backendProcess.Id). Backend: http://127.0.0.1:8000/docs"
Write-Host 'Frontend: http://localhost:3000. Press Ctrl+C to stop the frontend. Stop backend with its launcher PID if needed.'
& $frontendScript

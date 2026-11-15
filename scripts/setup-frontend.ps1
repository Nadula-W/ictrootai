$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location (Join-Path $projectRoot 'frontend')
if (!(Test-Path .env.local)) { Copy-Item .env.example .env.local }
npm ci
if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed' }
Write-Host 'Frontend ready.'

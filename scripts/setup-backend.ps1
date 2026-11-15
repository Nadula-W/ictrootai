$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location $projectRoot
New-Item -ItemType Directory -Force .tmp | Out-Null
$env:TEMP = Join-Path $projectRoot '.tmp'
$env:TMP = $env:TEMP
if (!(Test-Path backend/.venv/Scripts/python.exe)) {
    python -m venv backend/.venv
    if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed' }
}
if (!(Test-Path backend/.env)) { Copy-Item backend/.env.example backend/.env }
& backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
if (Test-Path curriculum/nie-ict-2017.pdf) {
    & backend/.venv/Scripts/python.exe scripts/extract_curriculum.py
    if ($LASTEXITCODE -ne 0) { throw 'Syllabus extraction failed' }
}
Set-Location backend
& .venv/Scripts/python.exe -m app.check_database
if ($LASTEXITCODE -ne 0) { throw 'Configure the Supabase connection in backend/.env before migrating. See docs/SUPABASE.md.' }
& .venv/Scripts/python.exe -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Migration failed' }
Write-Host 'Supabase schema ready. Import preserved local data or optionally run: .venv/Scripts/python.exe -m app.seed'

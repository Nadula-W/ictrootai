$ErrorActionPreference = 'Stop'
try {
    $result = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 5
    $result.models | Select-Object name, size, capabilities | Format-Table
    Write-Host 'Ollama reachable. No models were downloaded.'
} catch {
    Write-Error 'Ollama not reachable at 127.0.0.1:11434. Start the Ollama desktop app or run ollama serve.'
}

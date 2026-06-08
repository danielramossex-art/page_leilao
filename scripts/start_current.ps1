param(
    [int]$Port = 8512
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Get-CimInstance Win32_Process |
    Where-Object {
        $_.CommandLine -match "streamlit" -and
        $_.CommandLine -match "run" -and
        $_.CommandLine -match "app.py"
    } |
    ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }

Start-Process `
    -FilePath "python" `
    -ArgumentList @("-m", "streamlit", "run", "app.py", "--server.port", "$Port", "--server.address", "localhost", "--server.headless", "true") `
    -WorkingDirectory $ProjectRoot `
    -WindowStyle Hidden

Start-Sleep -Seconds 4
Write-Output "Busca Imóveis Leilão rodando em http://localhost:$Port"

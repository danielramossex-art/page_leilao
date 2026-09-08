param([int]$Port = 8512)
$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$AppPath = Join-Path $ProjectRoot "app.py"
# Stop only this project's server on the requested port.
Get-CimInstance Win32_Process |
    Where-Object {
        $_.CommandLine -and $_.CommandLine.Contains($AppPath) -and
        $_.CommandLine -match "streamlit.+run" -and
        $_.CommandLine -match "--server.port[ =]+$Port(?: |$)"
    } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
$LogDirectory = Join-Path $ProjectRoot "data/logs"
New-Item -ItemType Directory -Path $LogDirectory -Force | Out-Null
$LaunchOptions = @{
    FilePath = "python"
    ArgumentList = @("-m", "streamlit", "run", ('"{0}"' -f $AppPath), "--server.port", "$Port", "--server.address", "localhost", "--server.headless", "true")
    WorkingDirectory = $ProjectRoot
    WindowStyle = "Hidden"
    RedirectStandardOutput = (Join-Path $LogDirectory "current.stdout.log")
    RedirectStandardError = (Join-Path $LogDirectory "current.stderr.log")
    PassThru = $true
}
$Server = Start-Process @LaunchOptions
for ($Attempt = 0; $Attempt -lt 20; $Attempt++) {
    if ($Server.HasExited) { throw "O servidor encerrou. Consulte data/logs/current.stderr.log." }
    try {
        $Response = Invoke-WebRequest -Uri "http://localhost:$Port/_stcore/health" -UseBasicParsing -TimeoutSec 2
        if ($Response.StatusCode -eq 200) {
            Write-Output "Seach page Leilão disponível em http://localhost:$Port (PID $($Server.Id))"
            exit 0
        }
    } catch { }
    Start-Sleep -Seconds 1
}
throw "O servidor não respondeu. Consulte data/logs/current.stderr.log."

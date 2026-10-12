param([switch]$NoOpen)
$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
$taskUrl = 'http://127.0.0.1:18766/'
try {
    $taskHealth = Invoke-RestMethod ($taskUrl + 'health') -TimeoutSec 2
    if ($taskHealth.service -eq 'FrankVtuber') {
        if (-not $NoOpen) { Start-Process $taskUrl }
        exit 0
    }
} catch {}
$taskPython = Join-Path $taskRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    if (Get-Command py -ErrorAction SilentlyContinue) { & py -3 -m venv (Join-Path $taskRoot '.venv') }
    elseif (Test-Path -LiteralPath 'D:\Vtuber\.venv\Scripts\python.exe') {
        & 'D:\Vtuber\.venv\Scripts\python.exe' -m venv (Join-Path $taskRoot '.venv')
    } else { & python -m venv (Join-Path $taskRoot '.venv') }
    if ($LASTEXITCODE -ne 0) { throw 'Instala Python 3.12 o posterior y vuelve a iniciar.' }
    & $taskPython -m pip install -r (Join-Path $taskRoot 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las dependencias.' }
}
$taskSettings = Join-Path $taskRoot 'settings.json'
if (-not (Test-Path -LiteralPath $taskSettings)) {
    $taskConfig = @{ threshold = -50; last_hero = 'base'; hero_mode = 'auto' }
    if (Test-Path -LiteralPath 'D:\Vtuber\settings.json') {
        $taskPrior = Get-Content -Raw -LiteralPath 'D:\Vtuber\settings.json' | ConvertFrom-Json
        if ($taskPrior.microphone_endpoint) { $taskConfig.microphone_endpoint = $taskPrior.microphone_endpoint }
    }
    $taskConfig | ConvertTo-Json | Set-Content -LiteralPath $taskSettings -Encoding utf8
}
Start-Process -FilePath $taskPython -ArgumentList @('"' + (Join-Path $taskRoot 'avatar_server.py') + '"') -WorkingDirectory $taskRoot -WindowStyle Hidden
if (-not $NoOpen) {
    for ($taskAttempt = 0; $taskAttempt -lt 20; $taskAttempt++) {
        Start-Sleep -Milliseconds 250
        try { if ((Invoke-RestMethod ($taskUrl + 'health') -TimeoutSec 1).service -eq 'FrankVtuber') { Start-Process $taskUrl; break } } catch {}
    }
}

param(
    [string]$Url = "http://localhost:8000"
)

$ErrorActionPreference = "Stop"

$cloudflared = "C:\Program Files (x86)\cloudflared\cloudflared.exe"
if (-not (Test-Path $cloudflared)) {
    $command = Get-Command cloudflared -ErrorAction SilentlyContinue
    if ($command) {
        $cloudflared = $command.Source
    }
}
if (-not (Test-Path $cloudflared)) {
    throw "cloudflared.exe was not found. Install Cloudflare.cloudflared with winget first."
}

$projectRoot = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $projectRoot "storage\tunnel"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$logPath = Join-Path $logDir "cloudflared.log"
"[$timestamp] Starting quick tunnel for $Url" | Tee-Object -FilePath $logPath

& $cloudflared tunnel --url $Url --no-autoupdate 2>&1 | Tee-Object -FilePath $logPath -Append

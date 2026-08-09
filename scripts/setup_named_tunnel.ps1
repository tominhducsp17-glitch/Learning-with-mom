param(
    [Parameter(Mandatory = $true)]
    [string]$Hostname,

    [string]$TunnelName = "math-exam-agent"
)

$ErrorActionPreference = "Stop"

function Find-Cloudflared {
    $knownPath = "C:\Program Files (x86)\cloudflared\cloudflared.exe"
    if (Test-Path $knownPath) {
        return $knownPath
    }
    $command = Get-Command cloudflared -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }
    throw "cloudflared.exe was not found. Install it with: winget install --id Cloudflare.cloudflared -e"
}

function Ensure-DockerPath {
    $dockerBin = Join-Path $env:LOCALAPPDATA "Programs\DockerDesktop\resources\bin"
    if (Test-Path $dockerBin) {
        $env:PATH = "$dockerBin;$env:PATH"
    }
}

function Upsert-EnvValue {
    param(
        [string]$Path,
        [string]$Name,
        [string]$Value
    )

    if (-not (Test-Path $Path)) {
        Copy-Item ".env.production.example" $Path
    }
    $envText = Get-Content $Path -Raw
    if ($envText -match "(?m)^$Name=") {
        $envText = $envText -replace "(?m)^$Name=.*$", "$Name=$Value"
    } else {
        $envText = $envText.TrimEnd() + "`n$Name=$Value`n"
    }
    Set-Content -Path $Path -Value $envText -Encoding UTF8
}

$cloudflared = Find-Cloudflared
Ensure-DockerPath

$hostnameValue = $Hostname.Trim().TrimEnd("/")
if ($hostnameValue.StartsWith("http://") -or $hostnameValue.StartsWith("https://")) {
    $hostnameValue = ([Uri]$hostnameValue).Host
}
if (-not $hostnameValue.Contains(".")) {
    throw "Hostname must be a real domain/subdomain, for example hoc.example.com."
}

$cloudflaredDir = Join-Path $env:USERPROFILE ".cloudflared"
New-Item -ItemType Directory -Force -Path $cloudflaredDir | Out-Null
$certPath = Join-Path $cloudflaredDir "cert.pem"

if (-not (Test-Path $certPath)) {
    Write-Host "Cloudflare login is required. A browser window will open." -ForegroundColor Yellow
    Write-Host "Choose the Cloudflare account and the domain/zone for $hostnameValue, then return here." -ForegroundColor Yellow
    & $cloudflared tunnel login
}

$tunnelId = ""
$listRaw = & $cloudflared tunnel list --output json 2>$null
if ($LASTEXITCODE -eq 0 -and $listRaw) {
    $tunnels = $listRaw | ConvertFrom-Json
    $existing = @($tunnels) | Where-Object { $_.name -eq $TunnelName -and -not $_.deleted_at } | Select-Object -First 1
    if ($existing) {
        $tunnelId = $existing.id
    }
}

if (-not $tunnelId) {
    Write-Host "Creating Cloudflare tunnel: $TunnelName" -ForegroundColor Cyan
    $createOutput = & $cloudflared tunnel create $TunnelName 2>&1
    Write-Output $createOutput
    $listRaw = & $cloudflared tunnel list --output json
    $tunnels = $listRaw | ConvertFrom-Json
    $created = @($tunnels) | Where-Object { $_.name -eq $TunnelName -and -not $_.deleted_at } | Select-Object -First 1
    if (-not $created) {
        throw "Could not find the created tunnel named $TunnelName."
    }
    $tunnelId = $created.id
}

$credentialPath = Join-Path $cloudflaredDir "$tunnelId.json"
if (-not (Test-Path $credentialPath)) {
    throw "Tunnel credentials file was not found: $credentialPath"
}

$configPath = Join-Path $cloudflaredDir "math-exam-agent.yml"
$configContent = @"
tunnel: $tunnelId
credentials-file: /etc/cloudflared/$tunnelId.json

ingress:
  - hostname: $hostnameValue
    service: http://host.docker.internal:8000
  - service: http_status:404
"@
Set-Content -Path $configPath -Value $configContent -Encoding UTF8

Write-Host "Creating/updating DNS route for $hostnameValue" -ForegroundColor Cyan
& $cloudflared tunnel route dns $TunnelName $hostnameValue

Upsert-EnvValue -Path ".env.production" -Name "PUBLIC_BASE_URL" -Value "https://$hostnameValue"

Write-Host ""
Write-Host "Named tunnel configured." -ForegroundColor Green
Write-Host "Hostname: https://$hostnameValue"
Write-Host "Tunnel name: $TunnelName"
Write-Host "Tunnel id: $tunnelId"
Write-Host ""
Write-Host "Next command:" -ForegroundColor Green
Write-Host ".\scripts\start_named_tunnel_docker.ps1"

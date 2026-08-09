param(
    [string]$ConfigName = "math-exam-agent.yml"
)

$ErrorActionPreference = "Stop"

$dockerBin = Join-Path $env:LOCALAPPDATA "Programs\DockerDesktop\resources\bin"
if (Test-Path $dockerBin) {
    $env:PATH = "$dockerBin;$env:PATH"
}

$cloudflaredDir = Join-Path $env:USERPROFILE ".cloudflared"
$configPath = Join-Path $cloudflaredDir $ConfigName
if (-not (Test-Path $configPath)) {
    throw "Named tunnel config was not found: $configPath. Run scripts\setup_named_tunnel.ps1 first."
}

docker compose up --build -d --force-recreate mathexam | Out-Null
docker rm -f mathexam-tunnel 2>$null | Out-Null
docker run -d `
    --name mathexam-tunnel `
    --restart unless-stopped `
    -v "${cloudflaredDir}:/etc/cloudflared:ro" `
    cloudflare/cloudflared:latest `
    tunnel --config "/etc/cloudflared/$ConfigName" run | Out-Null

Start-Sleep -Seconds 8
docker compose ps
docker ps --filter name=mathexam-tunnel --format "table {{.Names}}\t{{.Status}}"
cmd /c "docker logs mathexam-tunnel --tail 80 2>&1"

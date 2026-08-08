$ErrorActionPreference = "Stop"

$dockerBin = Join-Path $env:LOCALAPPDATA "Programs\DockerDesktop\resources\bin"
if (Test-Path $dockerBin) {
    $env:PATH = "$dockerBin;$env:PATH"
}

docker rm -f mathexam-tunnel 2>$null | Out-Null
docker run -d --name mathexam-tunnel --restart unless-stopped cloudflare/cloudflared:latest tunnel --url http://host.docker.internal:8000 --no-autoupdate | Out-Null
Start-Sleep -Seconds 8
docker logs mathexam-tunnel --tail 120

$ErrorActionPreference = "Stop"

$dockerBin = Join-Path $env:LOCALAPPDATA "Programs\DockerDesktop\resources\bin"
if (Test-Path $dockerBin) {
    $env:PATH = "$dockerBin;$env:PATH"
}

docker rm -f mathexam-tunnel 2>$null | Out-Null
docker run -d --name mathexam-tunnel --restart unless-stopped cloudflare/cloudflared:latest tunnel --url http://host.docker.internal:8000 --no-autoupdate | Out-Null

$publicUrl = ""
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    $logs = cmd /c "docker logs mathexam-tunnel 2>&1"
    $match = [regex]::Match(($logs -join "`n"), "https://[-a-zA-Z0-9.]+trycloudflare.com")
    if ($match.Success) {
        $publicUrl = $match.Value
        break
    }
}

if (-not $publicUrl) {
    cmd /c "docker logs mathexam-tunnel --tail 120 2>&1"
    throw "Could not find the Cloudflare tunnel URL in container logs."
}

$envPath = Join-Path (Get-Location) ".env.production"
if (-not (Test-Path $envPath)) {
    Copy-Item ".env.production.example" $envPath
}

$envText = Get-Content $envPath -Raw
if ($envText -match "(?m)^PUBLIC_BASE_URL=") {
    $envText = $envText -replace "(?m)^PUBLIC_BASE_URL=.*$", "PUBLIC_BASE_URL=$publicUrl"
} else {
    $envText = $envText.TrimEnd() + "`nPUBLIC_BASE_URL=$publicUrl`n"
}
Set-Content -Path $envPath -Value $envText -Encoding UTF8

docker compose up --build -d --force-recreate mathexam | Out-Null
Start-Sleep -Seconds 5

Write-Host ""
Write-Host "Public URL:" -ForegroundColor Green
Write-Host $publicUrl
Write-Host ""
Write-Host "Student link format:" -ForegroundColor Green
Write-Host "$publicUrl/#student/AZT-XXXXXX"
Write-Host ""
docker compose ps

# Public test tunnel

Use this only for quick classroom testing before renting a VPS. It exposes the local Docker app through a random Cloudflare `trycloudflare.com` URL.

## Start the app

```powershell
$env:PATH = "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin;$env:PATH"
docker compose up -d
```

Check health:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health | ConvertTo-Json -Depth 4
```

## Start a public tunnel

Quick command:

```powershell
.\scripts\start_public_tunnel_docker.ps1
```

The script automatically writes the generated tunnel URL to `.env.production` as `PUBLIC_BASE_URL` and recreates the app container. After that, the teacher screen will show/copy student links with the public domain.

Manual command:

```powershell
$env:PATH = "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin;$env:PATH"
docker rm -f mathexam-tunnel 2>$null
docker run -d --name mathexam-tunnel --restart unless-stopped cloudflare/cloudflared:latest tunnel --url http://host.docker.internal:8000 --no-autoupdate
docker logs mathexam-tunnel --tail 120
```

Copy the generated URL ending in `.trycloudflare.com`.

If using the manual command, also set `PUBLIC_BASE_URL` in `.env.production` and restart the app:

```powershell
PUBLIC_BASE_URL=https://YOUR-TUNNEL.trycloudflare.com
docker compose up --build -d --force-recreate mathexam
```

## Share with students

Do not share the root URL while the app has no teacher login. Share only the student assignment URL shown in the teacher screen:

```text
https://YOUR-TUNNEL.trycloudflare.com/#student/AZT-XXXXXX
```

The quick tunnel URL changes when the tunnel is recreated. For stable URLs, use a named Cloudflare Tunnel or a VPS.

## Stop the tunnel

Quick command:

```powershell
.\scripts\stop_public_tunnel_docker.ps1
```

Manual command:

```powershell
$env:PATH = "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin;$env:PATH"
docker rm -f mathexam-tunnel
```

## Notes

- The Windows computer and Docker Desktop must stay on while students are using the app.
- SQLite data and uploaded files stay in the local `storage/` folder.
- Quick tunnels are for testing/development and have no uptime guarantee.
- Before a real public test, add teacher/admin login or share links only with a small trusted group.

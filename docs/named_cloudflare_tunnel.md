# Cloudflare Named Tunnel

Use this when a class needs a stable public URL, but the app is still running from the Windows computer at home.

Compared with Quick Tunnel:

- The URL is stable because it uses your own domain/subdomain.
- The app still depends on the Windows computer, Docker Desktop, and the home network staying on.
- Moving to a VPS later is simple: keep the same hostname and run the same app/tunnel on the VPS, or point DNS to the VPS.

## Cost

Cloudflare Tunnel can be used on Cloudflare's free plans. A domain name usually costs money yearly unless you already own one.

## Prerequisites

1. A Cloudflare account.
2. A domain added to Cloudflare, for example `example.com`.
3. A subdomain to use for this app, for example `hoc.example.com`.
4. Docker Desktop running.

## One-time setup

Run this from the project folder:

```powershell
.\scripts\setup_named_tunnel.ps1 -Hostname hoc.example.com
```

Replace `hoc.example.com` with your real subdomain.

The script will:

1. Open Cloudflare login in the browser if this machine is not authenticated yet.
2. Create or reuse a tunnel named `math-exam-agent`.
3. Create/update the DNS route for the hostname.
4. Write `PUBLIC_BASE_URL=https://hoc.example.com` to `.env.production`.
5. Create a config file under `%USERPROFILE%\.cloudflared\math-exam-agent.yml`.

## Start the app and tunnel

```powershell
.\scripts\start_named_tunnel_docker.ps1
```

Then open:

```text
https://hoc.example.com
```

Student links in the teacher screen should now be stable:

```text
https://hoc.example.com/#student/AZT-XXXXXX
```

## Stop only the tunnel

```powershell
.\scripts\stop_tunnel_docker.ps1
```

## Move to VPS later

There are two easy paths:

1. Keep Cloudflare Tunnel:
   - Copy the project to the VPS.
   - Set the same `PUBLIC_BASE_URL`.
   - Run the app and tunnel from the VPS.

2. Use normal DNS:
   - Point the hostname to the VPS IP.
   - Run Docker Compose on the VPS behind Nginx/Caddy.
   - Keep `PUBLIC_BASE_URL=https://hoc.example.com`.

The application code does not need to change.

## Safety notes

- Do not share the teacher/root URL widely before adding teacher login.
- For a small trusted test group, share only student assignment links.
- The Windows computer must not sleep during a test session.

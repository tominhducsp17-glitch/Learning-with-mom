# Deploy on Railway

Railway is a practical cloud test target before renting a VPS. It can deploy the existing Dockerfile and gives the app a public `*.up.railway.app` URL.

Important: this app stores SQLite, uploaded DOCX files, extracted formula images, and OCR assets under `/app/storage`. You must attach a Railway volume mounted at `/app/storage`, otherwise data can disappear after redeploy/restart.

## What is already prepared

- `Dockerfile` builds the React frontend and FastAPI backend into one container.
- The container listens on Railway's `PORT` variable.
- `railway.json` sets Dockerfile build and healthcheck path `/api/health`.
- App data path defaults to `/app/storage`, which matches the required volume mount.

## Manual steps in Railway

1. Open Railway and create a **New Project**.
2. Choose **Deploy from GitHub repo**.
3. Select `tominhducsp17-glitch/Learning-with-mom`.
4. Railway should detect the root `Dockerfile`.
5. Wait for the first deploy to start, then open the service.

## Add a volume

In the Railway service:

1. Open the service.
2. Go to **Volumes**.
3. Add a volume.
4. Set mount path exactly:

```text
/app/storage
```

This keeps SQLite and uploaded files across redeploys.

## Set environment variables

In the service variables, add:

```env
APP_ENV=production
MATH_EXAM_STORAGE_ROOT=/app/storage
MATH_EXAM_DATABASE_PATH=/app/storage/math_exam.sqlite3
MAX_UPLOAD_MB=25
MAGICK_BINARY=convert
MATH_EXAM_CUSTOM_FONT_DIR=/usr/local/share/fonts/mathexam

ADMIN_USERNAME=0912311121
ADMIN_PASSWORD=your_initial_admin_password
ADMIN_SESSION_DAYS=7

AUTO_OCR_ON_IMPORT=true
AUTO_OCR_MAX_WORKERS=2
AUTO_OCR_BATCH_SIZE=10

AI_PROVIDER=gemini
AI_PROVIDER_CHAIN=gemini,openrouter,nvidia
CHAT_PROVIDER_CHAIN=gemini,openrouter,nvidia

GEMINI_API_KEY=your_gemini_key_here
GEMINI_API_KEYS=
GEMINI_MODEL=gemini-3.1-flash-lite

OPENROUTER_API_KEY=
OPENROUTER_OCR_MODEL=nvidia/nemotron-nano-12b-v2-vl:free
OPENROUTER_CHAT_MODEL=nvidia/nemotron-nano-12b-v2-vl:free

NVIDIA_API_KEY=
NVIDIA_OCR_MODEL=nvidia/nemotron-ocr-v2
NVIDIA_OCR_BASE_URL=
NVIDIA_CHAT_MODEL=nvidia/nemotron-3-nano-30b-a3b

OPENAI_API_KEY=
OPENAI_MODEL=gpt-5-mini
```

`ADMIN_PASSWORD` chỉ được dùng để tạo tài khoản khi database chưa có admin. Sau lần đăng nhập đầu tiên, có thể đổi mật khẩu trong menu tài khoản giáo viên; mật khẩu mới được băm trong SQLite và không cần ghi lại vào Railway.

For Railway's smaller free/trial resources, start with:

```env
AUTO_OCR_MAX_WORKERS=2
AUTO_OCR_BATCH_SIZE=10
```

This is slower than local Docker but less likely to run out of memory.

### Provider fallback

OCR and chatbot now use separate fallback chains:

- `AI_PROVIDER_CHAIN`: used for formula OCR during import/manual OCR.
- `CHAT_PROVIDER_CHAIN`: used for the student explanation chatbot after submission.

Recommended trial setup:

```env
AI_PROVIDER_CHAIN=gemini,openrouter,nvidia
CHAT_PROVIDER_CHAIN=gemini,openrouter,nvidia
```

Notes:

- Gemini runs first because it has been tested most with the Word formula workflow.
- OpenRouter is the easiest extra fallback. Add `OPENROUTER_API_KEY` and keep:

```env
OPENROUTER_OCR_MODEL=nvidia/nemotron-nano-12b-v2-vl:free
OPENROUTER_CHAT_MODEL=nvidia/nemotron-nano-12b-v2-vl:free
```

- NVIDIA chatbot can run with only `NVIDIA_API_KEY`.
- NVIDIA direct OCR uses `nvidia/nemotron-ocr-v2`, but it needs a live NIM OCR endpoint. Leave `NVIDIA_OCR_BASE_URL` empty unless you have deployed/hosted that endpoint; the app will skip NVIDIA for OCR when this URL is empty.

For production stability later, use one paid provider with a clear monthly budget, then keep the free keys only as emergency fallback.

## Generate a public URL

In Railway service settings/networking:

1. Generate a Railway public domain.
2. Copy the generated URL, for example:

```text
https://your-app-name.up.railway.app
```

3. Add/update this variable:

```env
PUBLIC_BASE_URL=https://your-app-name.up.railway.app
```

4. Redeploy/restart the service.

Student links shown in the teacher screen should then look like:

```text
https://your-app-name.up.railway.app/#student/AZT-XXXXXX
```

## Health check

Open:

```text
https://your-app-name.up.railway.app/api/health
```

Expected:

```json
{"status":"ok"}
```

The response should also show:

- `storage.path` is `/app/storage`
- `database.path` is `/app/storage/math_exam.sqlite3`
- `converter.available` is `true`
- `converter.wmf` is `true`
- `ai.gemini_configured` is `true`

## Test checklist

1. Open the teacher page and log in with the admin account.
2. Upload the sample DOCX.
3. Confirm OCR finishes or press `OCR de` / `OCR sot` if needed.
4. Create/save class roster.
5. Assign the exam.
6. Open the student link from the teacher screen.
7. Submit as one student.
8. Check teacher results.
9. If answers are public, test chatbot from the student result page.

## Known risks on Railway free/trial

- The container is heavy because it includes LibreOffice and ImageMagick.
- The first Docker build can take several minutes because LibreOffice is large.
- OCR can be slow or hit memory limits on small plans.
- Free/trial credits may run out.
- Volume size is limited on small plans.
- Custom Microsoft-style fonts in the local `fonts/` folder are ignored by git for licensing/safety. Railway will use the open fonts installed in the Docker image unless you intentionally add licensed fonts later.

If Railway works for one class but feels slow, the next stable step is a small VPS.

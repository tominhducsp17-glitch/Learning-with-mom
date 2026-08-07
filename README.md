# Học cùng cô Tuyết

MathExam spark MVP: chuyển đề Toán `.docx` theo form Azota thành đề thi có cấu trúc, cho giáo viên duyệt, giao lớp và cho học sinh làm bài trên web.

## Trạng thái hiện tại

- Phase 0: cấu trúc project, fixture, test vàng cho file mẫu.
- Phase 1: DOCX parser đọc 3 phần đề, bảng đáp án, inline image/WMF/EMF và metadata kích thước Word.
- Phase 2: upload/review đề, sửa nội dung, đáp án, điểm, lưu bản nháp SQLite.
- Phase 3 đã có MVP: lớp học demo, mã giao bài, giao diện học sinh, đếm ngược thời gian, tự nộp khi hết giờ, dashboard giáo viên và thống kê cơ bản.
- Chưa làm AI sinh đề, chấm tự luận bằng AI, đăng nhập thật hoặc phân quyền sản xuất.

## Chạy local

Yêu cầu: Python 3.12+ và Node.js 20+.

```powershell
py -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
cd frontend
npm install
npm run build
cd ..
.\.venv\Scripts\python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Mở `http://127.0.0.1:8000`.

Khi phát triển frontend với hot reload:

```powershell
cd frontend
npm run dev
```

Sau đó mở `http://127.0.0.1:5173`; Vite sẽ proxy `/api` tới backend port 8000.

## Kiểm tra

```powershell
.\.venv\Scripts\python -m unittest discover backend\tests
cd frontend
npm run build
```

## Deploy thử bằng Docker

Yêu cầu: Docker Desktop hoặc Docker Engine có Compose plugin.

```powershell
Copy-Item .env.production.example .env.production
docker compose up --build
```

Mở `http://127.0.0.1:8000`.

Kiểm tra môi trường:

```text
http://127.0.0.1:8000/api/health
```

Khi deploy online, cần giữ persistent volume cho `storage/` vì SQLite database, file upload và ảnh công thức đều nằm ở đó. Xem thêm [deploy_note.md](deploy_note.md).

Parser CLI:

```powershell
py -m backend.app.services.parser.cli data\samples\de-mau-azota.docx `
  --assets-dir storage\extracted-assets\de-mau-azota `
  --output data\samples\de-mau-azota.parsed.json `
  --preview-output storage\previews\de-mau-azota.html `
  --convert-images
```

## Cấu hình

File `.env` dùng cho máy local và đã bị chặn trong `.gitignore`. File `.env.example` là mẫu có thể commit.

Hiện tại chưa cần API key để import, review, giao đề và làm bài. `OPENAI_API_KEY` được để sẵn cho các pha AI sau này.

## WMF/EMF

Parser giữ từng ảnh inline theo đúng vị trí trong Word. Nếu máy có ImageMagick hỗ trợ WMF/EMF, ảnh công thức được convert sang PNG nhưng vẫn hiển thị theo kích thước gốc của Word.

Nếu chưa convert được, parser tạo placeholder SVG và warning `UNCONVERTED_VECTOR_IMAGE` để không giả vờ parse thành công hoàn toàn.

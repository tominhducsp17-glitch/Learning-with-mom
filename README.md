# Học cùng cô Tuyết

MVP chuyển đề Toán `.docx` theo form Azota thành dữ liệu có cấu trúc để giáo viên duyệt và chỉnh sửa trước khi xuất bản.

## Trạng thái

- Phase 0: project structure, tài liệu kiến trúc và golden fixture.
- Phase 1: DOCX parser, 3 phần đề, 3 bảng đáp án, inline image/WMF và preview HTML.
- Phase 2 đang thực hiện: upload từ browser, review 22 câu, sửa nội dung/đáp án/điểm và lưu draft SQLite.
- Chưa có AI sinh đề, student runner, chấm tự luận hoặc dashboard.

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

Mở `http://127.0.0.1:8000`. Bản build React được FastAPI phục vụ trực tiếp.

Khi phát triển frontend với hot reload, chạy thêm tại `frontend/`:

```powershell
npm run dev
```

Sau đó mở `http://127.0.0.1:5173`; Vite sẽ chuyển tiếp `/api` tới backend port 8000.

## Chạy kiểm tra

```powershell
.\.venv\Scripts\python -m unittest discover backend\tests
cd frontend
npm run build
```

Parser CLI:

```powershell
py -m backend.app.services.parser.cli data\samples\de-mau-azota.docx `
  --assets-dir storage\extracted-assets\de-mau-azota `
  --output data\samples\de-mau-azota.parsed.json `
  --preview-output storage\previews\de-mau-azota.html
```

## Cấu hình local

File `.env` dùng cho máy local và đã được chặn trong `.gitignore`. File `.env.example` là mẫu cấu hình có thể commit lên Git.

Hiện tại chưa cần API key để import/review đề thi. Biến `OPENAI_API_KEY` được để sẵn cho các pha AI sau này.

## WMF/EMF

Máy hiện tại chưa có bộ chuyển WMF/EMF. Parser vẫn giữ file gốc, vị trí inline và tạo SVG placeholder kèm warning `UNCONVERTED_VECTOR_IMAGE`.

Để thử chuyển ảnh thật, cài ImageMagick có hỗ trợ WMF/EMF và import lại file. API đã bật chế độ thử convert tự động; CLI dùng thêm `--convert-images`.

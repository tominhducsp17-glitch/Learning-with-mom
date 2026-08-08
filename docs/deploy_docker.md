# Deploy Docker cho Học cùng cô Tuyết

Tài liệu này dùng cho bản MVP hiện tại: FastAPI phục vụ backend và frontend đã build, SQLite lưu dữ liệu, `storage/` lưu database, file upload và ảnh/công thức đã trích từ DOCX.

## Mục tiêu

- Chạy được app online cho 1 giáo viên và khoảng 200 học sinh.
- Giữ được dữ liệu sau khi restart container.
- Có môi trường convert/OCR công thức Word ổn định hơn máy local.
- Không commit API key thật lên Git.

## File liên quan

- `Dockerfile`: build frontend, cài Python backend, ImageMagick, LibreOffice và thư viện WMF.
- `docker-compose.yml`: chạy service `mathexam`, mount `./storage` và `./fonts`.
- `.env.production.example`: mẫu cấu hình production, được commit.
- `.env.production`: cấu hình thật, không commit.
- `storage/`: dữ liệu runtime, không commit.
- `fonts/`: font bổ sung nếu đề Word dùng MathType/Windows fonts.

## Cấu hình production

Tạo file thật từ mẫu:

```bash
cp .env.production.example .env.production
```

Trên Windows PowerShell:

```powershell
Copy-Item .env.production.example .env.production
```

Điền các biến quan trọng trong `.env.production`:

```env
APP_ENV=production
MATH_EXAM_STORAGE_ROOT=/app/storage
MATH_EXAM_DATABASE_PATH=/app/storage/math_exam.sqlite3
MAX_UPLOAD_MB=25

MAGICK_BINARY=convert
MATH_EXAM_CUSTOM_FONT_DIR=/usr/local/share/fonts/mathexam

AUTO_OCR_ON_IMPORT=true
AUTO_OCR_MAX_WORKERS=6
AUTO_OCR_BATCH_SIZE=20

AI_PROVIDER=gemini
GEMINI_API_KEY=dien_key_that_o_day
# Tùy chọn: thêm key dự phòng, cách nhau bằng dấu phẩy.
# App sẽ thử GEMINI_API_KEY trước, nếu gặp quota/rate-limit tạm thời thì thử các key dưới đây.
GEMINI_API_KEYS=key_du_phong_1,key_du_phong_2
GEMINI_MODEL=gemini-3.1-flash-lite

OPENAI_API_KEY=
OPENAI_MODEL=gpt-5-mini
```

Không đưa `.env.production` lên Git.

## Chạy thử production bằng Docker

Từ thư mục project:

```bash
docker compose up --build -d
```

Kiểm tra container:

```bash
docker compose ps
docker compose logs -f mathexam
```

Mở:

```text
http://127.0.0.1:8000
http://127.0.0.1:8000/api/health
```

Kết quả `/api/health` nên có:

- `status`: `ok` hoặc `degraded`.
- `storage.writable`: `true`.
- `database.parent_writable`: `true`.
- `ai.gemini_configured`: `true` nếu dùng Gemini OCR.
- `ai.auto_ocr_on_import`: `true` nếu muốn import đề là OCR luôn.
- `converter.available`: `true`.
- `converter.libreoffice.available`: `true`.
- `converter.custom_font_dir.exists`: `true`.

## Quy trình test sau khi deploy

1. Mở trang giáo viên.
2. Upload `đề mẫu azota.docx`.
3. Chờ OCR xong.
4. Nếu còn cảnh báo `AUTO_OCR_PARTIAL`, bấm `OCR sót` sau vài phút.
5. Kiểm tra PHẦN I, PHẦN II, PHẦN III đều hiển thị công thức nét.
6. Tạo lớp có vài học sinh demo.
7. Chọn thời gian làm bài.
8. Bật/tắt `Xem điểm`, `Xem đáp án` theo nhu cầu.
9. Giao bài.
10. Mở link học sinh trên trình duyệt khác hoặc điện thoại.
11. Làm thử, nộp bài.
12. Kiểm tra dashboard giáo viên, chi tiết bài nộp và xuất bảng điểm.

## Dữ liệu cần backup

Bắt buộc backup:

```text
storage/math_exam.sqlite3
storage/uploads/
storage/extracted-assets/
storage/previews/
```

Backup nhanh trên Linux:

```bash
mkdir -p backups
stamp=$(date +%Y%m%d-%H%M%S)
tar -czf "backups/math-exam-$stamp.tgz" storage
```

Restore:

```bash
docker compose down
tar -xzf backups/math-exam-YYYYMMDD-HHMMSS.tgz
docker compose up -d
```

## Nâng cấp phiên bản

Nếu deploy bằng Git trên VPS:

```bash
git pull
docker compose up --build -d
docker compose logs -f mathexam
```

Sau khi nâng cấp, mở `/api/health` và test lại một đề.

## Các lựa chọn deploy

### 1. VPS nhỏ

Khuyến nghị cho MVP thật.

Ưu điểm:

- Chủ động cài Docker, volume, backup.
- SQLite phù hợp hơn vì có ổ đĩa persistent rõ ràng.
- Dễ gắn domain và HTTPS bằng reverse proxy.

Nhược điểm:

- Cần tự quản lý server, backup, cập nhật bảo mật.

Phù hợp nếu chỉ có 1 giáo viên, khoảng 8 lớp, 200 học sinh.

### 2. Render, Railway, Fly.io

Phù hợp để demo nhanh nếu nền tảng hỗ trợ persistent disk/volume cho `storage/`.

Điểm cần kiểm tra trước khi chọn:

- Có persistent disk không.
- Disk có được mount vào `/app/storage` không.
- Có chạy được Dockerfile không.
- Có giới hạn sleep/free tier làm mất trải nghiệm không.
- Có hỗ trợ upload file và xử lý lâu đủ cho OCR không.

Nếu không có persistent storage ổn định, không nên dùng SQLite ở đó.

### 3. Máy tính ở nhà mở public tạm thời

Chỉ nên dùng để test ngắn.

Ưu điểm:

- Không mất phí server ngay.
- Dữ liệu nằm trên máy mình.

Nhược điểm:

- Cần mạng ổn định.
- Cần mở port hoặc dùng tunnel.
- Không phù hợp cho kỳ kiểm tra thật nếu máy ngủ, mất mạng hoặc đổi IP.

## SQLite hay PostgreSQL?

Giai đoạn này SQLite đủ dùng nếu:

- 1 giáo viên.
- Khoảng 200 học sinh.
- Không chạy nhiều container backend song song.
- Có backup định kỳ.
- Có persistent disk thật.

Nên chuyển PostgreSQL khi:

- Có nhiều giáo viên/admin.
- Muốn chạy nhiều backend instance.
- Lượng nộp bài đồng thời lớn.
- Cần phân quyền, audit log, báo cáo dài hạn, dữ liệu quan trọng hơn.

## Checklist trước khi cho dùng thật

- [ ] `.env.production` đã có API key thật và không bị commit.
- [ ] `docker compose up --build -d` chạy thành công.
- [ ] `/api/health` báo storage/database writable.
- [ ] Import đề mẫu không còn `UNCONVERTED_VECTOR_IMAGE`.
- [ ] Nếu có `AUTO_OCR_PARTIAL`, bấm `OCR sót` và kiểm tra lại.
- [ ] Giao bài thử cho lớp demo.
- [ ] Học sinh nộp thử trên điện thoại.
- [ ] Giáo viên xem dashboard, chi tiết bài nộp, xuất bảng điểm.
- [ ] Backup thử và restore thử `storage/`.

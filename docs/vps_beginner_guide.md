# VPS nhỏ là gì và deploy app này như thế nào?

Tài liệu này viết cho người không có nền dev/server.

## VPS là gì?

VPS có thể hiểu là một chiếc máy tính Linux thuê trên internet.

Khác với máy tính ở nhà:

- VPS bật 24/7.
- Có địa chỉ IP public để học sinh truy cập.
- Có ổ đĩa riêng để lưu database, file đề và ảnh công thức.
- Có thể gắn tên miền như `hoc-cung-co-tuyet.vn`.

Mình cài Docker lên VPS, rồi chạy app `Học cùng cô Tuyết` trong Docker. Khi đó giáo viên và học sinh chỉ cần mở trình duyệt, không cần cài Python, Node, ImageMagick hay font Toán.

## Vì sao không chỉ chạy local?

Chạy local phù hợp để phát triển và test.

Nhưng nếu cả lớp cùng dùng:

- Máy tính ở nhà phải luôn bật.
- Mạng nhà có thể đổi IP hoặc chặn port.
- Nếu máy ngủ/mất mạng, học sinh mất truy cập.
- Backup và HTTPS khó làm ổn định.

VPS giải quyết phần này bằng cách cho app sống trên một máy chủ nhỏ, chạy 24/7.

## Cấu hình VPS khuyến nghị cho MVP

Cho 1 giáo viên, khoảng 8 lớp, 200 học sinh:

- OS: Ubuntu 24.04 LTS hoặc Ubuntu 22.04 LTS.
- CPU: 2 vCPU.
- RAM: 4 GB.
- Disk: tối thiểu 40 GB SSD.
- Docker + Docker Compose plugin.
- Backup hằng ngày hoặc ít nhất trước/sau mỗi đợt kiểm tra.

Không cần GPU. OCR dùng API Gemini/OpenAI bên ngoài, server chỉ gửi ảnh công thức lên API.

## Nhà cung cấp nên chọn

Ưu tiên dễ dùng:

1. DigitalOcean
   - Dễ thao tác, tài liệu nhiều.
   - Giá thường cao hơn Hetzner một chút.
   - Hợp nếu muốn ít đau đầu.

2. Hetzner
   - Giá tốt, cấu hình mạnh.
   - Giao diện vẫn dễ dùng nhưng hơi kỹ thuật hơn DigitalOcean.
   - Hợp nếu muốn tiết kiệm.

3. Vultr
   - Cũng ổn, có nhiều region.
   - Có thể chọn nếu thanh toán/region tiện hơn.

Gợi ý của mình cho bản dùng thử thật: chọn VPS 2 vCPU / 4 GB RAM / 40 GB disk.

## Các bước bạn cần làm thủ công

Mình không thể tự làm các bước này nếu chưa có tài khoản/server:

1. Tạo tài khoản nhà cung cấp VPS.
2. Thêm phương thức thanh toán.
3. Tạo VPS Ubuntu.
4. Gửi cho agent thông tin kết nối SSH hoặc tự chạy lệnh theo hướng dẫn.
5. Nếu có domain, trỏ domain về IP của VPS.

## Các bước deploy trên VPS

Sau khi đã có VPS Ubuntu và đăng nhập SSH được:

```bash
sudo apt update
sudo apt install -y ca-certificates curl git
```

Cài Docker theo hướng dẫn chính thức của Docker cho Ubuntu, sau đó kiểm tra:

```bash
docker --version
docker compose version
```

Clone project:

```bash
git clone https://github.com/tominhducsp17-glitch/Learning-with-mom.git
cd Learning-with-mom
```

Tạo file cấu hình thật:

```bash
cp .env.production.example .env.production
nano .env.production
```

Điền key OCR:

```env
AI_PROVIDER=gemini
GEMINI_API_KEY=your_real_key_here
# Optional fallback keys, separated by comma.
GEMINI_API_KEYS=
GEMINI_MODEL=gemini-3.1-flash-lite
AUTO_OCR_ON_IMPORT=true
```

Chạy app:

```bash
docker compose up --build -d
docker compose ps
```

Mở thử:

```text
http://IP_CUA_VPS:8000
http://IP_CUA_VPS:8000/api/health
```

## Khi có domain

Nếu có domain, nên đặt reverse proxy HTTPS phía trước app, ví dụ Caddy hoặc Nginx.

Mô hình:

```text
hoc-cung-co-tuyet.vn -> Caddy/Nginx HTTPS -> app Docker port 8000
```

Giai đoạn test nội bộ có thể dùng tạm:

```text
http://IP_CUA_VPS:8000
```

Khi cho học sinh dùng thật, nên có HTTPS/domain.

## Backup dữ liệu

Dữ liệu quan trọng nằm trong `storage/`.

Backup nhanh:

```bash
mkdir -p backups
stamp=$(date +%Y%m%d-%H%M%S)
tar -czf "backups/math-exam-$stamp.tgz" storage
```

Nên tải file backup về máy cá nhân sau mỗi đợt kiểm tra.

## Khi cần cập nhật code

Trên VPS:

```bash
cd Learning-with-mom
git pull
docker compose up --build -d
docker compose ps
```

## Rủi ro cần nhớ

- Xóa VPS là mất dữ liệu nếu chưa backup.
- Xóa thư mục `storage/` là mất database và ảnh đề.
- Nếu API Gemini hết quota, OCR tự động có thể chậm hoặc báo partial.
- Nếu deploy trên free tier không có ổ đĩa persistent, SQLite có thể mất dữ liệu sau restart.

## Quyết định hiện tại

Cho MVP của mẹ dùng thử:

- Dùng VPS nhỏ.
- Dùng SQLite.
- Dùng Docker.
- Backup `storage/` thường xuyên.
- Chưa cần PostgreSQL.
- Chưa thêm chatbot trước khi chạy thử ổn luồng kiểm tra thật.

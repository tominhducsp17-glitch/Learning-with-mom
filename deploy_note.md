# Deploy Note

## WMF/EMF formula rendering

Loi hien thi placeholder tung gap tren macOS khong phu thuoc vao may hoc sinh hay trinh duyet. Loi do phu thuoc vao moi truong server/backend dung de doc DOCX va convert cong thuc Word.

Ket luan ngan:

- Hoc sinh va giao vien dung trinh duyet khong can cai ImageMagick.
- Server backend moi la noi doc DOCX va convert cong thuc/anh inline tu DOCX.
- ImageMagick co WMF/EMF la can thiet lam fallback, nhung tren Linux no co the render MathType WMF bi thieu chu/cong thuc trang.
- Ban Docker hien tai uu tien LibreOffice headless de render WMF MathType thanh anh, sau do parser luu thanh PNG va giu kich thuoc Word goc.
- Neu de Word dung MathType, nen cung cap font Windows/MathType trong thu muc `fonts/` local mount vao container, dac biet `MTEXTRA.TTF`, `symbol.ttf`, Times New Roman va Courier New.
- Neu server khong co converter hoac khong ho tro WMF/EMF, he thong van chay nhung parser se tao SVG placeholder va warning `UNCONVERTED_VECTOR_IMAGE`.
- Neu mot de da duoc import khi server chua co converter, sau khi cai converter can import/parse lai de do de tao lai asset PNG that.

## Deploy environment recommendation

Khong nen deploy backend theo kieu serverless/stateless neu dung SQLite va can luu asset cong thuc, vi he thong can o dia persistent cho:

- SQLite database file.
- Thu muc storage asset anh/cong thuc.
- File upload/source docx neu can giu lai.

Huong phu hop cho MVP:

- VPS nho hoac Docker tren server co persistent volume.
- SQLite truoc, vi quy mo 1 giao vien va khoang 200 hoc sinh van phu hop.
- Backup tu dong file SQLite va thu muc storage.
- Sau nay chuyen PostgreSQL khi co nhieu giao vien, nhieu backend instance, hoac tai dong thoi lon hon.

## Pre-deploy checklist

Truoc khi coi deploy la dat:

1. Backend health check bao ImageMagick ton tai.
2. Health check xac nhan WMF/EMF convert duoc.
3. Health check xac nhan `converter.libreoffice.available=true`.
4. Health check xac nhan `converter.custom_font_dir.font_count` co font neu de dung MathType/Windows fonts.
5. Health check xac nhan SQLite path doc/ghi duoc.
6. Health check xac nhan storage asset path doc/ghi duoc.
7. Import lai `de mau azota.docx` tren moi truong server.
8. Kiem tra khong con warning `UNCONVERTED_VECTOR_IMAGE`.
9. Mo giao dien giao vien va hoc sinh de xac nhan cong thuc hien thanh anh that, dung kich thuoc.

## Action item later

Truoc khi deploy online, nen Docker hoa moi truong hoac viet script cai dat server de dam bao moi truong production co day du converter, persistent storage va cau hinh database.

## Trial deploy flow

Da them cac file phuc vu deploy thu:

- `Dockerfile`
- `docker-compose.yml`
- `.env.production.example`

Chay thu tren may local co Docker:

```powershell
Copy-Item .env.production.example .env.production
docker compose up --build
```

Mo:

```text
http://127.0.0.1:8000
http://127.0.0.1:8000/api/health
```

Khi deploy len VPS:

1. Cai Docker va Docker Compose plugin tren server.
2. Copy source len server hoac pull tu Git.
3. Tao file `.env.production` tu `.env.production.example`.
4. Chay `docker compose up -d --build`.
5. Mo `/api/health` de kiem tra:
   - `storage.writable`
   - `database.parent_writable`
   - `converter.available`
   - `converter.wmf`
   - `converter.emf`
   - `converter.libreoffice.available`
   - `converter.custom_font_dir.font_count`
6. Import lai de mau de xac nhan khong con placeholder WMF/EMF.

Du lieu quan trong nam trong thu muc `storage/`, can backup ca thu muc nay. File SQLite mac dinh:

```text
storage/math_exam.sqlite3
```

Trong Docker Debian, ImageMagick 6 thuong dung binary `convert` thay vi `magick`, nen `.env.production` dat:

```text
MAGICK_BINARY=convert
```

Dockerfile hien tai cai them:

- `libmagickcore-6.q16-6-extra`, `libwmf-0.2-7`, `libwmf-bin` de tang kha nang ho tro WMF/EMF.
- `libreoffice-writer` de render DOCX/MathType WMF sang anh tot hon tren Linux.
- `fonts-dejavu-core`, `fonts-liberation2`, `fonts-urw-base35`, `fonts-opensymbol`, `xfonts-base` lam font fallback.

Thu muc `fonts/` duoc mount vao `/usr/local/share/fonts/mathexam`. Font that bi gitignore, khong commit len repo. Tren Windows local co the copy:

```text
C:\Windows\Fonts\MTEXTRA.TTF
C:\Windows\Fonts\symbol.ttf
C:\Windows\Fonts\times*.ttf
C:\Windows\Fonts\cour*.ttf
```

Neu health check bao `converter.available=false`, `converter.wmf=false`, `converter.libreoffice.available=false`, hoac font custom thieu voi de MathType, cong thuc Word co the hien placeholder hoac anh trang. Khi do can cai/doi image Docker, bo sung font, roi import lai de.

## High-DPI formula rendering

Pipeline render cong thuc:

1. LibreOffice headless convert DOCX → HTML, xuat anh cong thuc WMF/MathType thanh PNG/GIF theo kich thuoc Word goc.
2. ImageMagick upscale anh 3× voi filter `Point` (nearest-neighbor) — giu net canh cong thuc, khong bi mo.
3. Ket qua: file PNG co pixel 3 lan lon hon, nhung JSON van ghi `display_width_px` / `display_height_px` theo Word goc.
4. Frontend set `width`/`height` theo gia tri JSON → trinh duyet downscale anh 3× → hien thi sac net tren man hinh Retina / high-DPI.

Luu y:

- De import truoc khi co pipeline high-DPI van dung anh cu (kich thuoc 1×). Can import lai DOCX de co anh net.
- Tren may khong co ImageMagick, anh van dung duoc nhung khong upscale (giu nguyen kich thuoc LibreOffice xuat).
- He so 3× phu hop voi ca man hinh 2× (Retina) va 3× (Android flagship) ma khong tang dung luong qua nhieu.

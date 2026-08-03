# MathExam AI Agent - Ke hoach xay dung he thong tao de, cham trac nghiem va thong ke lop

## 1. Dinh huong tong quat

Du an duoc chon la:

**MathExam AI Agent: he thong ho tro giao vien Toan tao de thi tu file Word/PDF theo form Azota, giao de online, cham trac nghiem tu dong va thong ke ket qua theo lop.**

Nguoi dung dau tien la me cua chu du an: giao vien day Toan, can mot cong cu de:

- Tai file de mau len.
- He thong tu nhan dien cau hoi, dap an, cau dung va cau tra loi ngan.
- Tao de online cho tung lop.
- Hoc sinh lam bai tren dien thoai/may tinh.
- He thong cham diem tu dong va thong ke theo hoc sinh, theo cau, theo lop.

Day khong phai la mot chatbot hoc tap chung chung. Day la mot he thong workflow cho giao vien:

```text
Giao vien
  -> Upload de Word/PDF theo form
  -> Parser/OCR/Layout extractor
  -> AI review agent kiem tra cau hoi, dap an, loi form
  -> Exam builder
  -> Online test runner cho hoc sinh
  -> Auto grader
  -> Class analytics dashboard
```

Giai doan dau chi tap trung vao **he thong tao de thi tu de chuan form nhu file `de mau azota.docx`**, cham diem va thong ke theo lop. Cac tinh nang lon hon nhu ngan hang cau hoi, sinh de theo ma tran, app mobile, cham tu luan, LMS day du se de sau.

## 2. Bai toan san pham dang giai quyet

Trong cong viec hang ngay cua giao vien Toan, nhung viec ton thoi gian nhat la:

- Soan de theo dung form de co the dua len he thong.
- Tao de online tu file Word co nhieu cong thuc, hinh ve, bang dap an.
- Kiem tra loi nhan dien cau hoi/dap an sau khi upload.
- Giao de cho tung lop, nhac hoc sinh lam bai.
- Cham diem va tong hop ket qua.
- Xem cau nao hoc sinh sai nhieu de biet phan nao can giang lai.

He thong nay giai quyet bai toan:

**Bien file de Toan dang Word/PDF thanh mot bai kiem tra online co cau truc ro rang, cham duoc tu dong va co thong ke lop ngay sau khi hoc sinh nop bai.**

Gia tri san pham:

- Giam thoi gian tao de tu hang chuc phut xuong con vai phut.
- Giu duoc cong thuc Toan va dinh dang de goc.
- Giam loi khi giao/cham bai.
- Tao dashboard de giao vien nhin nhanh tinh hinh tung lop.
- Lam nen tang de sau nay them AI agent sinh cau hoi, phan tich loi sai va goi y on tap.

## 3. Tham chieu san pham Azota

Azota la tham chieu ve workflow, khong copy giao dien hay logic noi bo. Nguon cong khai cho thay Azota tap trung vao cac nhom tinh nang:

- So hoa de thi, bai tap, to chuc kiem tra online va quan ly diem/lop.
- Tao de tu Word, PDF, Excel, ngan hang cau hoi, kho de hoac sinh de theo ma tran.
- Chinh sua noi dung, chia diem, tao de con, dao cau hoi va dao dap an.
- Cham diem tu dong va tong hop ket qua.
- Quan ly hoc sinh, giao bai theo lop/nhom, theo doi tien do va ket qua.

Lien ket tham chieu:

- https://azota.vn/
- https://docs.azota.vn/docs/huong-dan-su-dung/de-thi/
- https://chamtracnghiem.azota.vn/

Quyet dinh cho MVP: khong lam day du nhu Azota ngay. Lam mot lat cat nho nhung that chac:

```text
Upload file de mau -> Parser tach cau hoi/dap an -> Giao vien review -> Tao bai thi online -> Hoc sinh lam -> Cham diem -> Thong ke theo lop
```

## 4. Phan tich file mau `de mau azota.docx`

File mau trong workspace:

```text
D:\Learn with mom\de mau azota.docx
```

Luu y: ten file that co dau tieng Viet la `de mau azota.docx` voi chu "de" co dau trong Windows Explorer.

Ket qua doc cau truc:

- Document co 144 paragraphs.
- Co 3 bang dap an.
- Co 184 media files dang `word/media/*.wmf`.
- Co 185 drawing objects.
- Khong co OMML equation (`m:oMath = 0`), nghia la cong thuc Toan dang duoc nhung nhu anh/WMF, khong phai equation text de parse truc tiep.

Cau truc de:

```text
Tieu de:
  DE KIEM TRA GIUA KY 1 SO 5

PHAN I:
  Cau trac nghiem nhieu phuong an lua chon
  12 cau
  Moi cau co 4 dap an A, B, C, D

PHAN II:
  Cau trac nghiem dung/sai
  4 cau
  Moi cau co 4 y a), b), c), d)
  Moi y chon Dung hoac Sai

PHAN III:
  Cau trac nghiem tra loi ngan
  6 cau
  Hoc sinh nhap dap an ngan, co the la so nguyen, so thap phan, phan so hoac bieu thuc ngan

Bang dap an:
  PHAN I: 12 dap an A/B/C/D
  PHAN II: 4 cau x 4 y, moi y D/S
  PHAN III: 6 dap an ngan
```

Dap an doc duoc tu bang trong file:

```text
PHAN I:
1:B, 2:D, 3:B, 4:A, 5:C, 6:B, 7:B, 8:A, 9:C, 10:B, 11:D, 12:C

PHAN II:
Cau 1: a:S, b:D, c:S, d:D
Cau 2: a:D, b:S, c:D, d:S
Cau 3: a:S, b:D, c:S, d:S
Cau 4: a:S, b:D, c:S, d:D

PHAN III:
1:63, 2:3, 3:0,88, 4:15, 5:9, 6:4,1
```

He qua ky thuat quan trong:

- Parser khong duoc chi dung text extraction vi cong thuc se bi mat.
- Can giu lai drawing/image inline theo dung thu tu trong paragraph.
- Nen render cong thuc/WMF thanh PNG/SVG hoac giu anh goc va gan placeholder vao noi dung cau hoi.
- AI agent co the ho tro kiem tra cau truc, nhung khong nen de LLM la nguon duy nhat de cham diem.

## 5. Lat cat MVP can lam truoc

MVP nen lam that chac mot workflow:

```text
Giao vien upload file Word de Toan theo form Azota
  -> he thong nhan dien 3 phan cua de
  -> tach cau hoi, lua chon, dap an dung
  -> hien man hinh review de giao vien sua loi
  -> tao bai thi online cho mot lop
  -> hoc sinh lam bai
  -> he thong cham diem
  -> dashboard thong ke ket qua theo lop
```

Non-goals trong MVP:

- Chua can app mobile native.
- Chua can ngan hang cau hoi lon.
- Chua can sinh de moi tu AI.
- Chua can cham tu luan dai.
- Chua can thanh toan, goi premium, phan quyen nha truong phuc tap.
- Chua can chong gian lan nang cao bang camera.
- Chua can import moi loai file tren doi; chi uu tien `.docx` theo form mau, sau do moi them PDF.

Muc prototype nham toi:

- Backend that.
- Parser that cho file Word mau.
- UI web that cho giao vien va hoc sinh.
- LLM/agent dung o vai tro augment: ho tro nhan dien loi form, goi y sua cau hoi, sinh giai thich thong ke.
- Cham diem deterministic bang dap an da parse va/hoac giao vien xac nhan.

## 6. Nguoi dung va job-to-be-done

### Giao vien

Job:

```text
Khi toi da co file de Toan Word/PDF, toi muon dua no thanh bai kiem tra online that nhanh, giao cho lop va xem ket qua sau khi hoc sinh nop bai.
```

Can:

- Upload file de.
- Xem he thong da nhan dien dung cau hoi chua.
- Sua nhanh cau bi nhan sai.
- Dat thang diem, thoi gian lam bai, lop nhan de.
- Xem hoc sinh nao da lam/chua lam.
- Xem diem, cau sai nhieu, pho diem, ty le dung theo cau.

### Hoc sinh

Job:

```text
Khi thay/co giao bai kiem tra, toi muon mo link, lam bai ro rang tren dien thoai/may tinh va nop bai khong bi roi dap an.
```

Can:

- Vao bai bang link/ma lop.
- Nhap ho ten hoac dang nhap nhe.
- Tra loi A/B/C/D, Dung/Sai, tra loi ngan.
- Xem trang thai cau da lam/chua lam.
- Nop bai va nhan ket qua neu giao vien cho phep.

## 7. Kien truc he thong de xuat

```text
Frontend Web
  - Teacher dashboard
  - Exam import/review
  - Student test runner
  - Analytics dashboard

Backend API
  - Auth/users/classes/students
  - File upload
  - Exam parser service
  - Exam/session management
  - Submission/grading service
  - Analytics service

AI Agent Layer
  - Form validation agent
  - Question cleanup assistant
  - Answer key sanity checker
  - Analytics insight generator

Storage
  - PostgreSQL/SQLite for data
  - Object storage/local file storage for uploaded DOCX and extracted images
  - Parsed exam JSON version history
```

### Stack khuyen nghi cho MVP

Frontend:

- React + Vite hoac Next.js.
- TypeScript.
- Tailwind CSS hoac shadcn/ui neu repo da dung.
- Math rendering: KaTeX/MathJax cho LaTeX sau nay, nhung MVP phai ho tro anh cong thuc.

Backend:

- FastAPI Python neu uu tien parser/AI nhanh.
- Hoac Next.js API routes neu muon full-stack TypeScript.
- Khuyen nghi thuc dung: FastAPI + React/Vite de parser docx/OCR de lam hon.

Database:

- SQLite cho local MVP.
- PostgreSQL khi trien khai online that.

Parser:

- `python-docx` de doc paragraph/table co ban.
- OOXML zip parser de giu thu tu text + drawing.
- Convert WMF/EMF/image sang PNG neu can hien thi web.
- PDF support sau: render page -> OCR/layout detect.

AI/LLM:

- OpenAI API hoac provider tuong duong.
- Dung tool-calling ro rang.
- LLM chi de review/sua/phan tich, khong cham diem neu dap an da co.

## 8. Data model toi thieu

### Quyet dinh database

Du an **can co database** ngay tu MVP, vi day khong chi la tool parse file mot lan. He thong can luu lop hoc, hoc sinh, de thi, cau hoi, dap an, bai da giao, bai nop va thong ke diem.

Khuyen nghi chot:

```text
Giai doan 1 local/MVP:
  SQLite

Giai doan deploy dung that:
  PostgreSQL
```

Ly do bat dau bang SQLite:

- Khong can cai database server rieng.
- Chay local de dang trong VS Code/Codex.
- Du de lam prototype end-to-end.
- Van co the migrate sang PostgreSQL neu dung ORM va schema ro rang.

Neu backend la Python FastAPI:

- Uu tien SQLAlchemy hoac SQLModel.
- Dung Alembic neu can migration.

Neu full-stack Next.js:

- Uu tien Prisma.
- Ban dau co the dung SQLite provider, sau doi sang PostgreSQL provider.

Nguyen tac schema:

- Khong luu de thi chi trong file JSON roi thoi.
- File JSON parsed co the luu lam artifact/version, nhung entity chinh van can nam trong database.
- Thiet ke id, quan he bang, timestamp va status ro de sau nay them thong ke, regrade va audit log.

```text
User
  id
  name
  role: teacher | student | admin
  phone/email optional

Class
  id
  teacher_id
  name
  school_year

Student
  id
  class_id
  name
  code optional

Exam
  id
  teacher_id
  title
  source_file_id
  status: draft | reviewed | published | archived
  duration_minutes
  scoring_config
  created_at

ExamSection
  id
  exam_id
  type: single_choice | true_false | short_answer
  title
  order_index

Question
  id
  section_id
  number
  prompt_blocks
  options
  correct_answer
  score
  difficulty optional
  tags optional

ExamAssignment
  id
  exam_id
  class_id
  start_at
  end_at
  allow_show_score

Submission
  id
  exam_assignment_id
  student_id
  started_at
  submitted_at
  answers
  score
  grading_detail

QuestionStat
  question_id
  total_submissions
  correct_count
  wrong_count
  correct_rate
```

### Dinh dang `prompt_blocks`

Khong nen luu prompt la mot string duy nhat vi de Toan co cong thuc/anh inline. Nen dung block model:

```json
[
  { "type": "text", "text": "Trong khong gian voi he toa do" },
  { "type": "image", "asset_id": "img_001", "alt": "cong thuc toa do Oxyz" },
  { "type": "text", "text": "cho duong thang" },
  { "type": "image", "asset_id": "img_002", "alt": "phuong trinh duong thang" }
]
```

Sau nay neu OCR/LLM convert duoc cong thuc sang LaTeX, co the them:

```json
{ "type": "math", "latex": "\\frac{x-1}{2}=\\frac{y+3}{-1}=\\frac{z}{4}" }
```

## 9. Parser pipeline cho file Word

### Dau vao

- `.docx` theo form Azota hoac gan giong.
- Co 3 phan:
  - PHAN I: trac nghiem A/B/C/D.
  - PHAN II: dung/sai a/b/c/d.
  - PHAN III: tra loi ngan.
- Co bang dap an o cuoi file.

### Dau ra

```json
{
  "title": "DE KIEM TRA GIUA KY 1 SO 5",
  "sections": [
    {
      "type": "single_choice",
      "questions": [
        {
          "number": 1,
          "prompt_blocks": [],
          "options": {
            "A": [],
            "B": [],
            "C": [],
            "D": []
          },
          "correct_answer": "B"
        }
      ]
    }
  ],
  "warnings": []
}
```

### Buoc thuc hien

1. Giai nen `.docx` nhu zip.
2. Doc `word/document.xml`.
3. Duyet body theo thu tu paragraph/table.
4. Trong moi paragraph, giu thu tu run:
   - text run -> block text
   - drawing/image -> block image voi `asset_id`
5. Copy media tu `word/media` sang folder asset cua exam.
6. Convert WMF sang PNG neu browser khong hien duoc truc tiep.
7. Nhan dien section bang cac heading:
   - `PHAN I`
   - `PHAN II`
   - `PHAN III`
8. Nhan dien cau hoi bang regex linh hoat:
   - `^Câu\s+\d+[:.]`
   - Chap nhan `Cau` khong dau.
9. Nhan dien option:
   - `A.`, `B.`, `C.`, `D.`
   - Co the nam tren cung mot dong, cach nhau bang tab.
10. Nhan dien bang dap an:
   - Bang PHAN I: hang `Cau`, hang `Chon`.
   - Bang PHAN II: 4 cot tuong ung cau 1-4, moi cot co a/b/c/d D/S.
   - Bang PHAN III: hang `Cau`, hang `Chon`.
11. Merge dap an vao cau hoi.
12. Tao warning neu:
   - Thieu dap an.
   - So cau parse khac so cau trong heading.
   - Cau co it hon/nhieu hon 4 lua chon.
   - Cong thuc/anh khong convert duoc.
   - Dap an ngan co dau phay thap phan can normalize.

### Acceptance cho parser MVP

Voi file mau:

- Parse duoc title.
- Parse duoc 12 cau PHAN I.
- Parse duoc 4 cau PHAN II, moi cau 4 y.
- Parse duoc 6 cau PHAN III.
- Doc dung 12 dap an PHAN I.
- Doc dung 16 dap an D/S PHAN II.
- Doc dung 6 dap an ngan PHAN III.
- Hien thi duoc cong thuc/anh trong UI review, khong bi mat noi dung.

## 10. Cham diem

### Thang diem de xuat cho MVP

Mac dinh:

```text
Tong diem: 10
PHAN I: 12 cau x 0.25 = 3.0 diem
PHAN II: 4 cau x 1.0 = 4.0 diem
  Moi y a/b/c/d dung: 0.25 diem
PHAN III: 6 cau x 0.5 = 3.0 diem
```

Cho giao vien sua diem tung phan/tung cau trong UI review.

### Rule cham

PHAN I:

- Dung dap an A/B/C/D -> duoc diem cau.
- Khong chon hoac chon sai -> 0.

PHAN II:

- Moi y D/S cham rieng.
- Diem cau = tong diem cac y dung.

PHAN III:

- Normalize dap an:
  - trim space
  - doi dau phay thap phan thanh dau cham de so sanh so hoc
  - `4,1` bang `4.1`
  - co the chap nhan sai so nho neu la so thap phan, vi du `epsilon = 1e-6`
- Giai doan dau chi cham exact/numeric match.
- Sau nay co the them AI-assisted grading cho bieu thuc tuong duong, nhung phai co che do giao vien review.

## 11. UI/UX product concept

UI can than thien voi giao vien, it chu, ro viec can lam. Khong lam landing page cho MVP. Man hinh dau tien sau login la dashboard lam viec.

### Teacher dashboard

Bo cuc:

```text
Top bar:
  Ten he thong, lop dang chon, nut tao de moi, tai khoan

Left sidebar:
  Lop hoc
  De thi
  Bai da giao
  Hoc sinh
  Thong ke

Main area:
  Danh sach de gan day
  Trang thai bai da giao
  Nut "Tao de tu file Word"
```

Tinh cach UI:

- Don gian, sang, ro nut hanh dong.
- Dung ngon ngu cua giao vien: "Tao de", "Giao bai", "Cham diem", "Thong ke lop".
- Khong hien qua nhieu cau hinh nang cao trong buoc dau.

### Exam import/review screen

Flow:

```text
1. Upload file
2. Dang xu ly
3. Review cau hoi
4. Sua dap an/thang diem
5. Luu de nhap
6. Giao cho lop
```

Layout review:

```text
Left:
  Danh sach cau hoi theo phan
  Badge canh bao neu cau co loi parse

Center:
  Noi dung cau hoi render gan giong file goc
  Option A/B/C/D hoac D/S hoac o tra loi ngan

Right:
  Dap an dung
  Diem cau
  Nut sua nhanh
  Canh bao parser/AI
```

### Student test runner

Can co:

- Header co ten de, thoi gian con lai, nut nop bai.
- Danh sach cau de nhay nhanh.
- Cau dang lam hien ro.
- Option lon, bam duoc tren dien thoai.
- Tu dong luu tam cau tra loi.
- Canh bao truoc khi nop neu con cau chua lam.

### Analytics dashboard

Can co:

- Bang diem hoc sinh.
- Pho diem.
- Diem trung binh, cao nhat, thap nhat.
- Ty le hoan thanh bai.
- Ty le dung theo cau.
- Top cau sai nhieu.
- Loc theo lop, de thi, lan giao.
- Xuat CSV/Excel.

## 12. AI agent nen lam gi va khong nen lam gi

### Nen lam

Form validation agent:

- Doc parsed JSON.
- Tim cau thieu option, thieu dap an, cau bi cat ky tu.
- Phat hien bang dap an khong khop so cau.
- Giai thich loi bang ngon ngu de giao vien sua nhanh.

Question cleanup assistant:

- Goi y sua loi chinh ta nhe.
- Goi y chuan hoa "Cau", "PHAN", option A/B/C/D.
- Khong tu sua dap an neu khong co xac nhan.

Analytics insight agent:

- Tom tat sau khi cham:
  - Lop lam tot/yeu phan nao.
  - Cau nao sai nhieu.
  - Goi y giao vien on lai chu de nao.

### Khong nen lam trong MVP

- Khong de LLM tu quyet dinh dap an dung neu file da co bang dap an.
- Khong cham tra loi ngan mo bang LLM khi chua co giao vien review.
- Khong tu sinh de moi va giao cho hoc sinh khi giao vien chua duyet.
- Khong sua noi dung cau hoi goc ma khong ghi version va cho giao vien xac nhan.

### Tool-calling interface de xuat

```text
parse_docx_exam(file_id) -> parsed_exam_json
validate_exam(parsed_exam_json) -> warnings
update_question(question_id, patch) -> question
publish_exam(exam_id, class_id, settings) -> assignment
grade_submission(submission_id) -> grading_result
get_class_analytics(assignment_id) -> analytics
generate_teacher_insights(analytics) -> summary
```

## 13. Kieu loi can thiet ke truoc

Parser errors:

- Khong doc duoc file.
- File khong phai `.docx`.
- Khong tim thay PHAN I/II/III.
- So cau parse duoc khac so cau mong doi.
- Option A/B/C/D nam cung dong nen tach sai.
- Cong thuc dang WMF khong convert duoc.
- Bang dap an bi thieu hoac sai format.

Teacher workflow errors:

- Giao vien upload nham file.
- Giao vien chua review da muon giao de.
- Thang diem khong tong bang 10.
- Giao de nham lop.

Student errors:

- Hoc sinh mat mang khi dang lam.
- Hoc sinh bam back/refresh.
- Hoc sinh nop bai khi con cau chua lam.
- Hoc sinh nhap dap an ngan `4,1` thay vi `4.1`.

Grading/statistics errors:

- Submission bi duplicate.
- Hoc sinh nop qua han.
- Dap an ngan co nhieu cach viet.
- Lop chua co hoc sinh nao nop nhung dashboard van phai hien trang thai rong dep.

## 14. Bao mat va rieng tu

MVP van can cac nguyen tac toi thieu:

- Giao vien chi xem du lieu lop cua minh.
- Hoc sinh chi lam bai duoc giao.
- Link bai thi nen co token/assignment code.
- File de upload luu rieng theo giao vien.
- Khong gui toan bo du lieu hoc sinh cho LLM neu khong can.
- Neu goi LLM de phan tich thong ke, chi gui du lieu da toi thieu hoa/an danh neu co the.
- Co audit log cho cac hanh dong: upload, sua dap an, publish, nop bai, cham lai.

## 15. Lo trinh thuc hien

### Cach chia thanh cac lan thuc hien voi Codex Agent

Du an nen chia thanh nhieu lan thuc hien nho. Moi lan phai co ket qua chay duoc hoac artifact kiem tra duoc, tranh giao mot prompt qua rong.

De co MVP dau tien, du kien can khoang **6 lan thuc hien chinh**:

```text
Lan 1: Phase 0 + Phase 1
  Tao project structure, setup backend, doc file mau, xay DOCX parser,
  tao JSON/test fixture cho file mau.

Lan 2: Phase 2
  Lam UI giao vien: upload file, xem ket qua parse,
  review/sua cau hoi, dap an va diem.

Lan 3: Database + luu de thi
  Gan SQLite, tao schema, luu exam/classes/students/questions
  tu parsed JSON vao database.

Lan 4: Phase 3
  Tao lop, them hoc sinh, giao de, tao link lam bai,
  lam giao dien hoc sinh.

Lan 5: Phase 4
  Cham diem tu dong:
  trac nghiem A/B/C/D, dung/sai, tra loi ngan.

Lan 6: Phase 5
  Dashboard thong ke lop:
  bang diem, ty le dung theo cau, cau sai nhieu, pho diem, export CSV.
```

Sau 6 lan nay, he thong nen co ban MVP co the dung thu end-to-end:

```text
Upload de Word -> review -> luu de -> giao cho lop -> hoc sinh lam -> cham diem -> xem thong ke
```

Sau MVP, tiep tuc cac lan nang cap:

```text
Lan 7: Polish UI/UX
  Responsive mobile, loading/error/empty states, trai nghiem giao vien/hoc sinh muot hon.

Lan 8: AI agent review de
  Phat hien loi form, thieu dap an, option tach sai, goi y sua cau hoi.

Lan 9: AI phan tich ket qua lop
  Tom tat cau sai nhieu, chu de yeu, goi y phan can on lai.

Lan 10: Deploy online
  Auth that, PostgreSQL, backup du lieu, cau hinh production.
```

Quy tac khi giao viec cho Codex Agent:

- Moi lan chi giao 1-2 phase lien quan gan nhau.
- Uu tien parser va data model truoc UI nang cao.
- Khong lam AI sinh de truoc khi workflow upload -> cham diem chay duoc.
- Sau moi lan, yeu cau agent chay test/script va bao cao ro:
  - Da lam duoc gi.
  - File nao da tao/sua.
  - Lenh nao da chay.
  - Loi/warning con lai.
  - Prompt goi y cho lan tiep theo.

### Phase 0 - Chuan bi repo va tai lieu

Muc tieu:

- Tao project structure.
- Doc file spec nay.
- Chot stack thuc te.
- Tao sample data tu file mau.

Cong viec:

- Tao repo/app neu chua co.
- Tao `docs/architecture.md`.
- Tao `docs/parser_contract.md`.
- Tao `data/samples/` va copy file de mau vao do.
- Tao JSON expected output cho file mau.

Tieu chi hoan thanh:

- Co README chay local.
- Co file sample exam JSON.
- Co checklist parser acceptance.

### Phase 1 - DOCX parser

Muc tieu:

- Parse duoc file Word mau thanh JSON co cau hoi, dap an, anh cong thuc.

Cong viec:

- Viet service/module docx parser.
- Duyet XML theo thu tu text + drawing.
- Trich xuat media.
- Convert/hien thi image asset.
- Parse 3 section.
- Parse 3 bang dap an.
- Viet test fixture cho file mau.

Tieu chi hoan thanh:

- Test pass voi file mau:
  - 12 single-choice questions.
  - 4 true/false questions.
  - 6 short-answer questions.
  - Answer key dung nhu muc 4.
- UI hoac preview HTML hien duoc noi dung khong mat cong thuc.

### Phase 2 - Teacher import/review UI

Muc tieu:

- Giao vien upload file va review ket qua parse.

Cong viec:

- Tao upload screen.
- Tao processing state.
- Tao review screen chia 3 phan.
- Cho sua cau hoi/dap an/diem.
- Hien warning parser/AI.
- Luu exam draft.

Tieu chi hoan thanh:

- Upload file mau tu browser.
- Xem duoc 22 cau theo dung phan.
- Sua dap an mot cau va luu lai duoc.

### Phase 3 - Exam publishing va student runner

Muc tieu:

- Giao de cho lop va hoc sinh lam bai online.

Cong viec:

- Tao class/student management toi thieu.
- Tao assignment link/code.
- Tao man hinh lam bai cho hoc sinh.
- Luu autosave answers.
- Nop bai.

Tieu chi hoan thanh:

- Tao lop 12A1.
- Them 3 hoc sinh demo.
- Giao de mau cho lop.
- Hoc sinh demo lam va nop bai duoc.

### Phase 4 - Auto grading

Muc tieu:

- Cham diem tu dong theo answer key.

Cong viec:

- Viet grading service deterministic.
- Ho tro 3 loai cau:
  - single_choice
  - true_false
  - short_answer numeric/string
- Luu grading_detail.
- Cho giao vien cham lai neu sua dap an.

Tieu chi hoan thanh:

- Submission demo duoc cham dung.
- Co diem tong va diem tung phan.
- Sua dap an -> regrade -> diem cap nhat.

### Phase 5 - Class analytics

Muc tieu:

- Thong ke ket qua theo lop.

Cong viec:

- Bang diem hoc sinh.
- Pho diem.
- Ty le dung theo cau.
- Top cau sai nhieu.
- Export CSV.
- Insight text do AI ho tro neu co API key.

Tieu chi hoan thanh:

- Giao vien xem duoc ket qua lop.
- Biet cau nao sai nhieu nhat.
- Xuat CSV duoc.

### Phase 6 - Polish va deploy

Muc tieu:

- Bien MVP thanh web app co the dung thu.

Cong viec:

- Cai auth don gian.
- Lam UI responsive cho dien thoai.
- Them loading/error/empty states.
- Viet seed data.
- Viet huong dan deploy.

Tieu chi hoan thanh:

- Chay local on dinh.
- Co demo end-to-end.
- Co README cho nguoi khac/coding agent tiep tuc.

## 16. Repo structure de xuat

```text
math-exam-agent/
  README.md
  docs/
    architecture.md
    parser_contract.md
    product_brief.md
    evaluation.md
  data/
    samples/
      de-mau-azota.docx
      de-mau-azota.expected.json
  backend/
    app/
      main.py
      config.py
      models/
      routers/
      services/
        parser/
        grading/
        analytics/
        ai_agent/
      tests/
  frontend/
    src/
      app/
      components/
      pages/
      lib/
      styles/
  storage/
    uploads/
    extracted-assets/
```

Neu chon Next.js full-stack, co the doi thanh:

```text
math-exam-agent/
  app/
  components/
  lib/
    parser/
    grading/
    analytics/
    ai/
  prisma/
  public/exam-assets/
  docs/
  data/samples/
```

Nhung neu parser `.docx` va OCR la trong tam, backend Python van de lam nhanh hon.

## 17. Testing strategy

Unit tests:

- Parser regex cau hoi.
- Parser dap an PHAN I.
- Parser dap an PHAN II.
- Parser dap an PHAN III.
- Normalize dap an ngan.
- Grading single_choice.
- Grading true_false.
- Grading short_answer.

Integration tests:

- Upload file mau -> parsed exam JSON.
- Publish exam -> create assignment.
- Submit answers -> grade -> analytics.

Golden test cho file mau:

```text
Expected:
  title contains "GIUA KY 1"
  section single_choice count = 12
  section true_false count = 4
  section short_answer count = 6
  answer_key part I = B,D,B,A,C,B,B,A,C,B,D,C
  answer_key part II = [[S,D,S,D], [D,S,D,S], [S,D,S,S], [S,D,S,D]]
  answer_key part III = [63, 3, 0.88, 15, 9, 4.1]
```

UI tests:

- Teacher upload page.
- Teacher review page khong tran text tren mobile.
- Student runner tren mobile.
- Analytics dashboard empty state va full state.

## 18. Chat prompt de dua cho coding agent

Prompt khoi dau:

```text
Doc file AZOTA_MATH_EXAM_AGENT_PLAN.md.
Bat dau thuc hien Phase 0 va Phase 1.
Uu tien xay docx parser cho file mau de mau azota.docx.
Khong lam AI sinh de va khong lam UI phuc tap truoc khi parser tao duoc JSON dung.
Parser phai giu duoc cong thuc/anh inline, vi file mau dung WMF/drawing cho cong thuc Toan.
Tao test golden cho file mau:
- 12 cau trac nghiem A/B/C/D
- 4 cau dung/sai, moi cau 4 y
- 6 cau tra loi ngan
- dap an dung nhu trong spec
Neu moi truong khong convert duoc WMF sang PNG, hay tao asset placeholder va ghi warning ro rang, khong gia vo parse thanh cong.
```

Prompt khi bat dau UI:

```text
Tiep tuc theo AZOTA_MATH_EXAM_AGENT_PLAN.md.
Thuc hien Phase 2: teacher import/review UI.
Man hinh dau tien can dung duoc ngay, khong lam landing page.
UI phai than thien voi giao vien: upload file, xem cau hoi theo 3 phan, sua dap an/diem, xem canh bao parser.
Dung du lieu parsed JSON tu Phase 1, khong mock neu parser da co output.
```

Prompt khi bat dau cham diem/thong ke:

```text
Tiep tuc theo AZOTA_MATH_EXAM_AGENT_PLAN.md.
Thuc hien Phase 4 va Phase 5.
Cham diem deterministic theo answer key da duoc giao vien review.
Ho tro single choice, true/false, short answer numeric.
Tao analytics theo lop: bang diem, pho diem, ty le dung theo cau, top cau sai nhieu, export CSV.
```

## 19. Quyet dinh ky thuat nen chot ngay

Khuyen nghi:

- MVP dung Python FastAPI cho backend va React/Vite cho frontend.
- Dung SQLite truoc, PostgreSQL sau.
- Parser `.docx` la uu tien so 1.
- Luu cau hoi bang `prompt_blocks`, khong luu string plain text.
- Giu anh cong thuc nhu first-class asset.
- LLM chi la assistant/reviewer, khong la grader chinh.
- Moi output parser phai co warnings va confidence.
- Giao vien luon co man hinh review truoc khi publish.

Thong diep san pham:

**Tu mot file de Toan Word co san, giao vien co the tao bai thi online, cham diem va xem thong ke lop ma khong phai sua tay tung cau.**

# Architecture

## Muc tieu hien tai

Phase 0/1 da co parser vung cho file DOCX mau `de-mau-azota.docx`. Phase 2 them teacher import/review UI toi thieu. AI sinh de, student runner, cham tu luan va dashboard de sang phase sau.

## Cau truc project

```text
math-exam-agent/
  README.md
  docs/
    architecture.md
    parser_contract.md
  data/
    samples/
      de-mau-azota.docx
      de-mau-azota.expected.json
  backend/
    app/
      main.py
      storage.py
      services/
        parser/
          docx_parser.py
          cli.py
    tests/
      test_docx_parser.py
      test_draft_store.py
  frontend/
    src/
      App.tsx
      api.ts
      types.ts
      index.css
  storage/
    uploads/
    extracted-assets/
    math_exam.sqlite3
```

## Pipeline parser

1. Mo `.docx` nhu ZIP.
2. Doc `word/document.xml` va `word/_rels/document.xml.rels`.
3. Duyet `w:body` theo thu tu paragraph/table.
4. Trong paragraph, giu thu tu run:
   - `w:t`, `w:tab`, `w:br` thanh text block.
   - `w:drawing`, `w:pict` thanh image block.
5. Copy media goc sang `storage/extracted-assets/<exam>/`.
6. Neu media la WMF/EMF, tao SVG placeholder va warning `UNCONVERTED_VECTOR_IMAGE`.
7. Tach 3 phan de, cau hoi, lua chon/menh de con.
8. Doc 3 bang dap an va merge vao cau hoi.
9. Validate count, dap an, option/subitem va asset conversion.

## Quyet dinh

- Dung Python stdlib de parser chay duoc ngay tren may hien tai.
- Luu noi dung cau hoi bang block model, khong ep thanh plain string.
- Khong de LLM doan dap an. Bang dap an trong file la nguon dung deterministic.
- FastAPI phuc vu upload, parser API, draft API va frontend production build.
- SQLite luu parsed JSON cua tung draft; khi save, `answer_keys` duoc tao lai tu dap an tung cau.
- React/Vite chi lam workflow import/review, khong co landing page hay dashboard.

# Parser Contract

## Input

- File `.docx` theo form Azota.
- Co 3 phan:
  - PHAN I: 12 cau trac nghiem A/B/C/D.
  - PHAN II: 4 cau dung/sai, moi cau 4 y a/b/c/d.
  - PHAN III: 6 cau tra loi ngan.
- Co 3 bang dap an o cuoi file.

## Output

```json
{
  "schema_version": "0.1",
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
  "assets": [],
  "warnings": []
}
```

## Block model

```json
{ "type": "text", "text": "Trong khong gian voi he toa do " }
```

```json
{
  "type": "image",
  "asset_id": "img_0001",
  "render_path": "storage/extracted-assets/de-mau-azota/img_0001.placeholder.svg",
  "original_path": "storage/extracted-assets/de-mau-azota/img_0001.wmf",
  "status": "placeholder"
}
```

## Warnings bat buoc

- `UNCONVERTED_VECTOR_IMAGE`: WMF/EMF duoc copy nhung chua convert duoc sang PNG/SVG that.
- `COUNT_MISMATCH`: so cau parse duoc khac expected.
- `MISSING_ANSWER`: cau khong co dap an trong bang dap an.
- `OPTION_COUNT_MISMATCH`: cau PHAN I khong co du 4 lua chon.
- `SUBITEM_COUNT_MISMATCH`: cau PHAN II khong co du 4 y a/b/c/d.

## Golden acceptance file mau

- PHAN I: 12 cau, dap an `B,D,B,A,C,B,B,A,C,B,D,C`.
- PHAN II:
  - Cau 1: `a:S, b:Đ, c:S, d:Đ`
  - Cau 2: `a:Đ, b:S, c:Đ, d:S`
  - Cau 3: `a:S, b:Đ, c:S, d:S`
  - Cau 4: `a:S, b:Đ, c:S, d:Đ`
- PHAN III: `63, 3, 0,88, 15, 9, 4,1`.

## Preview HTML

CLI co the tao preview HTML tu parsed JSON bang `--preview-output`. Preview nay khong phai dashboard; no chi la man hinh kiem tra nhanh de xem cau hoi, dap an va cac inline image/placeholder co nam dung vi tri trong cau hay khong.

## Optional image conversion

`--convert-images` se thu dung ImageMagick neu tim thay lenh `magick`. Khi convert that bai hoac khong co tool, parser phai giu `.wmf` goc, tao `.placeholder.svg` va them warning `UNCONVERTED_VECTOR_IMAGE`.

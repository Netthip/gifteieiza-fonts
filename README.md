# ฟอนต์ลายมือกิฟ — Gifteieiza ✍️

ฟอนต์ภาษาไทย + อังกฤษ ที่สร้างจากลายมือจริงของกิฟ (Netthip) ทุกตัวอักษร

## ⭐ Gifteieiza Blend — ตัวแนะนำ

![Gifteieiza Blend](gifteieiza-blend/specimen.png)

ตัวที่ดีที่สุดของแต่ละตัวอักษรจากลายมือ 4 แบบ ปรับให้เส้นหนา ขนาด และเส้นฐานเท่ากันทั้งชุด

- สระ–วรรณยุกต์ไม่ชนตัวอักษร (ตรวจครบ 2,438 แบบ) วรรณยุกต์ซ้อนสระแยกชั้นให้เอง เช่น กิ๊ฟ ที่ เสื้อ
- ใช้ใน Microsoft Word ได้ (ทดสอบแล้ว) และฝังฟอนต์ในไฟล์ Word/PDF ได้
- มี “ ” ‘ ’ … – — ที่ Word แปลงให้อัตโนมัติตอนพิมพ์

## ติดตั้ง

1. ดาวน์โหลด [GifteieizaBlend-Regular.ttf](gifteieiza-blend/GifteieizaBlend-Regular.ttf) (กด Download raw file)
2. ดับเบิลคลิกไฟล์ → กด **Install**
3. เลือกฟอนต์ **Gifteieiza Blend** ใน Word / PowerPoint / Photoshop ฯลฯ (ปิดเปิดโปรแกรมที่เปิดค้างอยู่ก่อน)

**Canva:** อัปโหลดไฟล์ .ttf ที่ Brand Kit → ฟอนต์ (ต้องมี Canva Pro)

## ทั้งตระกูล

| ฟอนต์ | คาแรกเตอร์ | ที่มา | อังกฤษ |
|---|---|---|---|
| ⭐ [**Gifteieiza Blend**](gifteieiza-blend/) | **ตัวแนะนำ** — ตัวที่ดีที่สุดจาก 4 สไตล์มินิ ปรับเป็นชุดเดียว | รวม Round/Slim/Firm/Soft | ✅ |
| [Gifteieiza](gifteieiza/) | ปากกาเมจิก เส้นชัดมั่นคง | แม่แบบใหญ่ 10 หน้า | ✅ |
| [Gifteieiza Pen](gifteieiza-pen/) | ปากกาลูกลื่น เส้นบางโปร่ง | แม่แบบใหญ่ (ชุดแรก) | ✅ |
| [Gifteieiza Round](gifteieiza-round/) | ตัวกลมหนา ขี้เล่น | แม่แบบมินิ | ✅ |
| [Gifteieiza Slim](gifteieiza-slim/) | เส้นเรียว สูงโปร่ง | แม่แบบมินิ | ✅ |
| [Gifteieiza Firm](gifteieiza-firm/) | ตรงคม อ่านง่าย | แม่แบบมินิ | ✅ |
| [Gifteieiza Soft](gifteieiza-soft/) | โค้งมนนุ่มนวล | แม่แบบมินิ | บางส่วน (ยังไม่มี T–Z a–z) |

ทุกตัว (v1.1): วรรณยุกต์ 2 ตำแหน่ง, สระบน/วรรณยุกต์หลบหาง ป ฝ ฟ ฬ, ฐ ญ หางห้อยใต้เส้น (ตัดหางเองเมื่อมีสระล่าง),
ใช้ใน Word ได้, ระยะบรรทัดคลุมวรรณยุกต์ซ้อนไม่โดนตัดหัว

**ยังไม่มีในทุกตัว:** `~ + = * $ < > ^ | { }` (ไม่มีในแม่แบบ — เขียนเพิ่มได้)

## เขียนลายมือสไตล์ใหม่

แม่แบบกระดาษอยู่ที่ [`handwriting-font/`](handwriting-font/) — แนะนำ `แม่แบบมินิ-2หน้าจบ.pdf`
(เขียน 2 หน้าได้ภาษาไทยครบ หน้า 3–4 อังกฤษ/ตัวเลข ทำหรือไม่ก็ได้) สแกน 600 dpi แล้วตัดตัวอักษรด้วย `tools/extract.py`

## สร้างฟอนต์ใหม่ทั้งตระกูล

```
python tools/rebuild_all.py            # ทุกตัว (Blend สร้างต่อท้ายให้เอง)
python tools/rebuild_all.py gifteieiza-soft
```

ต้องมี `fonttools pillow numpy scipy uharfbuzz` — เครื่องมืออยู่ที่ [`tools/`](tools/):
`build_font.py` (ประกอบ TTF + ระบบวรรณยุกต์), `blend.py` (รวม 4 สไตล์), `specimen.py` (ภาพตัวอย่าง),
`extract.py` + `geom*.json` (ตัดตัวอักษรจากสแกนแม่แบบ)

## ลิขสิทธิ์

ลายมือและฟอนต์ © 2026 กิฟ (Netthip) — สงวนสิทธิ์

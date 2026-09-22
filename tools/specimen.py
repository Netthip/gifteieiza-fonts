# -*- coding: utf-8 -*-
"""ภาพตัวอย่างฟอนต์ (specimen.png) จัดวางตัวอักษรด้วย HarfBuzz ตัวเดียวกับที่ Canva/เบราว์เซอร์ใช้
ใช้: python tools/specimen.py <ฟอนต์.ttf> <ภาพ.png>
ต้องมี: fonttools pillow uharfbuzz"""
import sys
import uharfbuzz as hb
from fontTools.ttLib import TTFont
from fontTools.pens.basePen import BasePen
from PIL import Image, ImageChops, ImageDraw

SS = 4          # วาดใหญ่ 4 เท่าแล้วย่อ ให้ขอบเนียน


class _Poly(BasePen):
    """แตกเส้นโค้งเป็นรูปหลายเหลี่ยม"""
    def __init__(self):
        super().__init__(None)
        self.polys, self.cur = [], []
    def _moveTo(self, p):
        self.cur = [p]
    def _lineTo(self, p):
        self.cur.append(p)
    def _qCurveToOne(self, p1, p2):
        p0 = self.cur[-1]
        for i in range(1, 9):
            t = i / 8
            self.cur.append(((1-t)**2*p0[0] + 2*(1-t)*t*p1[0] + t*t*p2[0],
                             (1-t)**2*p0[1] + 2*(1-t)*t*p1[1] + t*t*p2[1]))
    def _curveToOne(self, p1, p2, p3):
        self.cur.append(p3)
    def _closePath(self):
        if len(self.cur) > 2:
            self.polys.append(self.cur)
        self.cur = []
    _endPath = _closePath


def render_line(path, text, px):
    """คืนภาพโหมด L (หมึก=255) ของข้อความหนึ่งบรรทัด สูง px ต่อ em"""
    tt = TTFont(path)
    gs, order, upm = tt.getGlyphSet(), tt.getGlyphOrder(), tt["head"].unitsPerEm
    asc, desc = tt["hhea"].ascent, -tt["hhea"].descent
    font = hb.Font(hb.Face(hb.Blob.from_file_path(path)))
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf, {})
    s = px * SS / upm
    pad = 6 * SS
    W = int(sum(p.x_advance for p in buf.glyph_positions) * s) + 2 * pad
    H = int((asc + desc) * s) + 2 * pad
    img = Image.new("1", (W, H), 0)
    x = 0
    for inf, ps in zip(buf.glyph_infos, buf.glyph_positions):
        pen = _Poly()
        gs[order[inf.codepoint]].draw(pen)
        layer = Image.new("1", (W, H), 0)
        for poly in pen.polys:           # even-odd ภายในตัวเดียว (รูของ อ ก ฯลฯ)
            tmp = Image.new("1", (W, H), 0)
            ImageDraw.Draw(tmp).polygon([(pad + (x + ps.x_offset + px_) * s, pad + (asc - (py + ps.y_offset)) * s)
                                         for px_, py in poly], fill=1)
            layer = ImageChops.logical_xor(layer, tmp)
        img = ImageChops.logical_or(img, layer)   # ตัวที่เกยกันไม่หักล้างกัน
        x += ps.x_advance
    return img.convert("L").resize((W // SS, H // SS), Image.LANCZOS)


def supported(path, text):
    cmap = TTFont(path).getBestCmap()
    return all(ord(c) in cmap or c == " " for c in text)


def specimen(path, out):
    fam = str(TTFont(path)["name"].getName(1, 3, 1, 0x409))
    title = f"กิ๊ฟเขียนเอง — {fam}"
    if not supported(path, title):              # เช่น Soft ยังไม่มีตัวพิมพ์เล็กอังกฤษ
        title = "กิ๊ฟเขียนเอง — " + fam.split()[-1].upper() if supported(path, fam.upper()) else "กิ๊ฟเขียนเอง"
    lines = [(title, 58),
             ("สวัสดีค่ะ ฟอนต์ลายมือน่ารักๆ ที่สุดในโลก ๒๕๖๙ (2026) ปั้นปุ๊กปิ๊ก!", 34),
             ("ปีใหม่ ฟ้าใส ฝั่งโน้น ก็ อื่น ขึ้น ซึ่ง ถึง ฐาน รัฐบาล ญาติ บุญ …", 34)]
    ims = [render_line(path, t, px) for t, px in lines]
    W = max(1240, max(i.width for i in ims) + 36)
    H = sum(i.height for i in ims) + 30
    sheet = Image.new("L", (W, H), 255)
    y = 12
    for im in ims:
        sheet.paste(0, (18, y), im)             # หมึกดำตามรูปตัวอักษร
        y += im.height
    sheet.convert("RGB").save(out)
    print("specimen:", out, sheet.size)


if __name__ == "__main__":
    specimen(sys.argv[1], sys.argv[2])

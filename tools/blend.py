# -*- coding: utf-8 -*-
"""รวม 4 สไตล์จากแม่แบบมินิ (Round / Slim / Firm / Soft) เป็นฟอนต์เดียว: Gifteieiza Blend

ขั้นตอน
1. เลือกตัวอักษรรายตัว (PICK ข้างล่าง) — Soft เป็นแกน เพราะหัวกลมเปิดชัดและสม่ำเสมอที่สุด
   แล้วเอาตัวที่ดีกว่าจากสไตล์อื่นมาแทนเฉพาะตัว (เลือกจากคะแนนความเหมือนฉันทามติ 4 สไตล์ + ดูด้วยตา)
2. ปรับสัดส่วนแต่ละสไตล์ให้เข้ากัน: ความสูงหัวพยัญชนะ, เส้นฐาน, ความกว้าง (Firm กว้าง/Slim แคบ -> เข้าหาค่ากลาง)
   และขนาดสระ/วรรณยุกต์ให้เท่ากับค่ากลางของ 4 สไตล์
3. ปรับน้ำหนักเส้นให้เท่ากันทุกตัว: หาแกนกลางเส้น (thinning) แล้ววาดใหม่ด้วยวงกลมตามความหนาเดิม
   ที่ปรับสเกลเข้าหาน้ำหนักเป้าหมาย — รูปทรง/มุม/หัวทึบยังเหมือนลายมือเดิม แค่หนาเท่ากันทั้งชุด
4. เขียน glyphs/ + meta.json ใหม่ แล้วให้ build_font.py ประกอบ (ระบบวรรณยุกต์/หลบหาง/กันชนครบเหมือนตัวอื่น)

ใช้: python tools/blend.py   (ต้อง build 4 สไตล์ต้นทางก่อน — rebuild_all.py ทำให้ตามลำดับ)
ต้องมี: fonttools pillow numpy scipy"""
import json, math, os, subprocess, sys
import numpy as np
from PIL import Image, ImageChops, ImageDraw
from scipy import ndimage
from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "gifteieiza-blend")
FAMILY, TTF = "Gifteieiza Blend", "GifteieizaBlend-Regular.ttf"
SRC = {
    "Soft":  "gifteieiza-soft/GifteieizaSoft-Regular.ttf",
    "Round": "gifteieiza-round/GifteieizaRound-Regular.ttf",
    "Slim":  "gifteieiza-slim/GifteieizaSlim-Regular.ttf",
    "Firm":  "gifteieiza-firm/GifteieizaFirm-Regular.ttf",
}
FALLBACK = ["Soft", "Round", "Slim", "Firm"]      # สไตล์ที่เลือกไม่มีตัวนี้ -> ใช้ตามลำดับนี้

UPPER = "ัิีึื็ํ"
TONES = "่้๊๋์"
LOWER = "ุู"
LAT = "".join(chr(c) for c in range(0x41, 0x5B)) + "".join(chr(c) for c in range(0x61, 0x7B))

# ตัวที่ไม่ได้มาจาก Soft (ที่เหลือทั้งหมดใช้ Soft)
PICK = {
    # Round: หัวกลมสวย สัดส่วนสมดุล — ก ที่ใช้บ่อยที่สุดได้ Round, จ ฉ ฆ ฌ ณ Soft หัวทึบ/เบี้ยว
    # ฐ: หางของทุกสไตล์เป็นขยุกขยิก แต่ของ Round ตัวชัดสุด หางโปร่งสุด
    "Round": "กจฉฆฌณฐ" + "๒" + "\"'#%-@\\_",
    # Firm: เส้นเรียบร้อยสุดในตัวที่คนอื่นหัวทึบ (ฎ ฏ ฒ ล ส ห) + สระบน วรรณยุกต์ สระล่าง สะอาดสุด (ขยายขนาดให้เท่าค่ากลาง)
    "Firm": "ฎฏฒลสห" + UPPER + TONES + LOWER,
    # Slim: อ ฮ ฯ ๆ ขนาดพอดี ชัด + ตัวอังกฤษทั้งชุด (Soft ไม่มี T–Z a–z, Round มี f หน้าตาเหมือน t)
    "Slim": "อฮฯๆ" + LAT + "!?",
}
STYLE_OF = {ch: st for st, chars in PICK.items() for ch in chars}

R = 0.75                   # px ต่อหน่วยฟอนต์ ตอนวาดใหม่
W_TARGET = 47.0            # ความหนาเส้นเป้าหมาย (ค่ากลางของ 4 สไตล์: 44 44 50 50)
WIDTH_PULL = 0.6           # ดึงความกว้างเข้าหาค่ากลางกี่ส่วน (1 = เท่ากันเป๊ะ, 0 = ไม่ปรับ)
U_PER_MM = 560 / 24.0      # ให้ build_font.py (ค่าเริ่มต้น body-mm 24) แปลง px กลับเป็นหน่วยเดิมพอดี
BODY_REF = [chr(c) for c in range(0x0E01, 0x0E2F) if chr(c) not in "ฤฦปฝฟฬฎฏฐญ"]


class _Poly(BasePen):
    def __init__(self):
        super().__init__(None); self.polys, self.cur = [], []
    def _moveTo(self, p): self.cur = [p]
    def _lineTo(self, p): self.cur.append(p)
    def _qCurveToOne(self, p1, p2):
        p0 = self.cur[-1]
        for i in range(1, 9):
            t = i / 8
            self.cur.append(((1-t)**2*p0[0] + 2*(1-t)*t*p1[0] + t*t*p2[0], (1-t)**2*p0[1] + 2*(1-t)*t*p1[1] + t*t*p2[1]))
    def _curveToOne(self, p1, p2, p3): self.cur.append(p3)
    def _closePath(self):
        if len(self.cur) > 2: self.polys.append(self.cur)
        self.cur = []
    _endPath = _closePath


class Src:
    def __init__(self, path):
        self.tt = TTFont(path); self.gs = self.tt.getGlyphSet(); self.cmap = self.tt.getBestCmap()
    def name(self, ch, high=False):
        if high:
            n = "uni%04X.high" % ord(ch)
            return n if n in self.gs else None
        return self.cmap.get(ord(ch))
    def raster(self, name, pad=4):
        """บิตแมปของ glyph ที่ความละเอียด R: (mask, x ของคอลัมน์ 0, y ของแถว 0) หน่วยฟอนต์"""
        p = _Poly(); self.gs[name].draw(p)
        if not p.polys: return None, 0, 0
        xs = [x for q in p.polys for x, _ in q]; ys = [y for q in p.polys for _, y in q]
        x0, y1 = min(xs), max(ys)
        W = int(math.ceil((max(xs) - x0) * R)) + 2 * pad; H = int(math.ceil((y1 - min(ys)) * R)) + 2 * pad
        img = Image.new("1", (W, H), 0)
        for q in p.polys:
            tmp = Image.new("1", (W, H), 0)
            ImageDraw.Draw(tmp).polygon([(pad + (x - x0) * R, pad + (y1 - y) * R) for x, y in q], fill=1)
            img = ImageChops.logical_xor(img, tmp)
        return np.array(img, dtype=bool), x0 - pad / R, y1 + pad / R


def thin(mask):
    """Zhang–Suen thinning (vectorized) -> แกนกลางเส้นกว้าง 1 px"""
    img = np.pad(mask.astype(np.uint8), 1)
    while True:
        changed = False
        for step in (0, 1):
            P = img
            p2 = np.roll(P, 1, 0); p3 = np.roll(p2, -1, 1); p4 = np.roll(P, -1, 1); p5 = np.roll(p4, -1, 0)
            p6 = np.roll(P, -1, 0); p7 = np.roll(p6, 1, 1); p8 = np.roll(P, 1, 1); p9 = np.roll(p8, 1, 0)
            nb = [p2, p3, p4, p5, p6, p7, p8, p9]
            B = sum(n.astype(np.int16) for n in nb)
            seq = nb + [p2]
            A = sum(((seq[i] == 0) & (seq[i + 1] == 1)).astype(np.int16) for i in range(8))
            c = ((p2 * p4 * p6 == 0) & (p4 * p6 * p8 == 0)) if step == 0 else ((p2 * p4 * p8 == 0) & (p2 * p6 * p8 == 0))
            kill = (P == 1) & (B >= 2) & (B <= 6) & (A == 1) & c
            if kill.any():
                img = img.copy(); img[kill] = 0; changed = True
        if not changed:
            return img[1:-1, 1:-1].astype(bool)


def stroke_width(mask):
    dt = ndimage.distance_transform_edt(mask); sk = thin(mask)
    return 2 * float(np.median(dt[sk])) / R if sk.any() else 0.0


def style_stats(src):
    """ค่ากลางของพยัญชนะตัวสูงปกติ: ขอบล่าง, สูง, กว้าง, หนาเส้น + ขนาดสระบน/วรรณยุกต์/สระล่าง"""
    b, h, w, sw = [], [], [], []
    for ch in BODY_REF:
        n = src.name(ch)
        if not n: continue
        m, x0, yt = src.raster(n)
        ys, xs = np.nonzero(m)
        b.append(yt - (ys.max() + 1) / R); h.append((ys.max() - ys.min() + 1) / R)
        w.append((xs.max() - xs.min() + 1) / R); sw.append(stroke_width(m))
    def mark_h(chars, high=False):
        v = []
        for ch in chars:
            n = src.name(ch, high)
            if n:
                m, _, _ = src.raster(n); ys, _ = np.nonzero(m); v.append((ys.max() - ys.min() + 1) / R)
        return float(np.median(v)) if v else None
    return dict(bottom=float(np.median(b)), height=float(np.median(h)), width=float(np.median(w)),
                stroke=float(np.median(sw)), upper=mark_h(UPPER), tone=mark_h(TONES), lower=mark_h(LOWER))


def restroke(src, name, st, T, kind):
    """วาด glyph ใหม่: แกนกลางเส้น -> ปรับสัดส่วนสไตล์ -> วงกลมตามความหนาเดิมที่ปรับเข้าหาน้ำหนักเป้าหมาย"""
    m, x0, yt = src.raster(name)
    if m is None or not m.any(): return None
    dt = ndimage.distance_transform_edt(m)
    sk = thin(m)
    sy, sx = np.nonzero(sk)
    X = x0 + sx / R; Y = yt - sy / R                       # หน่วยฟอนต์
    rad = dt[sy, sx] / R * (W_TARGET / T[st]["w_s"])      # ความหนาเดิม -> ปรับสเกลเข้าหาเป้าหมาย
    rad = np.clip(rad, 0.8 * W_TARGET / 2, 1.8 * W_TARGET / 2)
    # สัดส่วนสไตล์: แกนกลางเส้นของพยัญชนะ [ขอบล่าง, ขอบบน] ของสไตล์นี้ -> ช่วงเป้าหมาย
    ky, kx, c0 = T[st]["ky"], T[st]["kx"], T[st]["c0"]
    Y = (Y - c0) * ky + W_TARGET / 2
    X = X * kx
    if kind in ("upper", "tone2", "lower"):               # สระ/วรรณยุกต์: ขยายให้เท่าค่ากลาง 4 สไตล์
        k = T[st]["mark_" + ("lower" if kind == "lower" else ("upper" if name[3:7] in [f"{ord(c):04X}" for c in UPPER] else "tone"))]
        cx = (X.min() + X.max()) / 2
        yref = Y.max() if kind == "lower" else Y.min()     # สระล่างยึดขอบบน, สระบน/วรรณยุกต์ยึดขอบล่าง
        X = cx + (X - cx) * k; Y = yref + (Y - yref) * k
    # วาดลงผืนใหม่
    pad = 4
    xmin, xmax = (X - rad).min(), (X + rad).max(); ymin, ymax = (Y - rad).min(), (Y + rad).max()
    W = int(math.ceil((xmax - xmin) * R)) + 2 * pad; H = int(math.ceil((ymax - ymin) * R)) + 2 * pad
    img = Image.new("L", (W, H), 0); d = ImageDraw.Draw(img)
    for x, y, r in zip(X, Y, rad):
        px, py, pr = pad + (x - xmin) * R, pad + (ymax - y) * R, r * R
        d.ellipse([px - pr, py - pr, px + pr, py + pr], fill=255)
    a = np.array(img) > 127
    ys, xs = np.nonzero(a)
    a = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    top_y = ymax + pad / R - ys.min() / R                  # y (หน่วยฟอนต์) ของแถวแรกหลังครอป
    return a, top_y


def main():
    srcs = {st: Src(os.path.join(ROOT, p)) for st, p in SRC.items()}
    stats = {st: style_stats(s) for st, s in srcs.items()}
    med = lambda k: float(np.median([s[k] for s in stats.values() if s[k]]))
    H_T = med("height"); WR_T = float(np.median([s["width"] / s["height"] for s in stats.values()]))
    T = {}
    for st, s in stats.items():
        ky = (H_T - W_TARGET) / (s["height"] - s["stroke"])
        full = (WR_T * H_T - W_TARGET) / (ky * (s["width"] - s["stroke"]))
        T[st] = dict(ky=ky, kx=ky * full ** WIDTH_PULL, c0=s["bottom"] + s["stroke"] / 2, w_s=s["stroke"],
                     mark_upper=(med("upper") / s["upper"]) if s["upper"] else 1.0,
                     mark_tone=(med("tone") / s["tone"]) if s["tone"] else 1.0,
                     mark_lower=(med("lower") / s["lower"]) if s["lower"] else 1.0)
        print(f"{st:<6} สูง {s['height']:.0f} กว้าง {s['width']:.0f} หนา {s['stroke']:.0f} ก้น {s['bottom']:+.0f}"
              f" -> ky {ky:.3f} kx {T[st]['kx']:.3f} | ขยายสระบน x{T[st]['mark_upper']:.2f} วรรณยุกต์ x{T[st]['mark_tone']:.2f} สระล่าง x{T[st]['mark_lower']:.2f}")
    print(f"เป้าหมาย: สูง {H_T:.0f} กว้าง/สูง {WR_T:.2f} หนา {W_TARGET:.0f}")

    gdir = os.path.join(OUT_DIR, "glyphs")
    os.makedirs(gdir, exist_ok=True)              # ไม่ลบทั้งโฟลเดอร์ (OneDrive ชอบล็อกโฟลเดอร์ไว้) ลบแค่ไฟล์เก่า
    for f in os.listdir(gdir):
        if f.endswith((".png", ".json")):
            os.remove(os.path.join(gdir, f))
    chars = sorted({chr(u) for s in srcs.values() for u in s.cmap
                    if u > 0x20 and u not in (0xA0, 0x2013, 0x2014, 0x2018, 0x2019, 0x201C, 0x201D, 0x2026)})
    meta, used = [], {}
    jobs = [(ch, False) for ch in chars] + [(ch, True) for ch in TONES]
    for ch, high in jobs:
        want = STYLE_OF.get(ch, "Soft")
        order = [want] + [s for s in FALLBACK if s != want]
        st = next((s for s in order if srcs[s].name(ch, high)), None)
        if st is None: continue
        kind = "tone2" if high else ("upper" if ch in UPPER + TONES else ("lower" if ch in LOWER else "base"))
        res = restroke(srcs[st], srcs[st].name(ch, high), st, T, kind)
        if res is None: continue
        a, top_y = res
        key = "u%04X" % ord(ch) + ("_high" if high else "")
        Image.fromarray(np.where(a, 255, 0).astype("uint8")).save(os.path.join(gdir, key + ".png"))
        meta.append(dict(key=key, ch=ch, type=kind, ppm=R * U_PER_MM, bbox_w=a.shape[1], bbox_h=a.shape[0],
                         base_dy=top_y * R, src=st))
        used[st] = used.get(st, 0) + 1
    json.dump(meta, open(os.path.join(gdir, "meta.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print("ตัวอักษร:", len(meta), "| มาจาก:", used)

    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "build_font.py"), "--glyphs", gdir,
                        "--family", FAMILY, "--out", os.path.join(OUT_DIR, TTF), "--spare", ""],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    print("\n".join(l for l in r.stdout.splitlines() if l.startswith(("win ", "ยก/กด", "missing: ['", "saved"))))
    if r.returncode:
        print(r.stderr[-2000:]); sys.exit(1)


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""ประกอบฟอนต์ Gifteieiza จาก glyphs_A (bitmap -> contour -> quadratic -> TTF + GSUB/GPOS)

v1.1: สระบน/วรรณยุกต์หลบหาง ป ฝ ฟ ฬ · จัดกึ่งกลางจากหมึกจริง (ไม่นับเศษหมึก) ·
      ตั้งค่า OS/2 ให้ Word รู้ว่ารองรับภาษาไทย + ฝังในไฟล์/Canva ได้ · ไม่ตัดหัว-ท้ายตัวสูง ·
      เพิ่ม ‘ ’ “ ” … – — (Word แปลงให้อัตโนมัติ) จากเส้นลายมือที่มีอยู่"""
import json, math, os
import numpy as np
from PIL import Image, ImageDraw
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.transformPen import TransformPen
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString

import argparse
ap = argparse.ArgumentParser()
ap.add_argument("--glyphs", default="glyphs_A")
ap.add_argument("--family", default="Gifteieiza")
ap.add_argument("--out", default="Gifteieiza-Regular.ttf")
ap.add_argument("--spare", default="spare_p4_1=ก")   # ช่องสำรองใช้แทนตัวไหน "key=char,..."
ap.add_argument("--snap", default="")                 # ตัวที่ต้องยกให้ก้นอยู่บนเส้นฐาน เช่น "ฐ"
ap.add_argument("--tail", default="")                 # ตัวที่เขียนหางไว้ในบรรทัด -> วางตัวบนเส้นฐาน ให้หางห้อยใต้เส้น เช่น "ญฐ"
ap.add_argument("--scale-to", type=float, default=0)  # ขยายทั้งชุดให้หัวพยัญชนะ (median) สูงเท่านี้ (0=ปิด)
ap.add_argument("--tighten", action="store_true")     # ดึงสระ/วรรณยุกต์ลงชิดหัวอักษรจริง + วางฐานให้แตะเส้น
ap.add_argument("--body-mm", type=float, default=24.0)  # ความสูงช่วงพยัญชนะของแม่แบบ (มินิ = 14.5)
ap.add_argument("--dump-fea", default="")              # เขียนไฟล์ features.fea ไว้ดู (ว่าง = ไม่เขียน)
A = ap.parse_args()

SCRATCH = os.path.dirname(os.path.abspath(__file__))
GD = os.path.join(SCRATCH, A.glyphs)
OUT_TTF = os.path.join(SCRATCH, A.out)
SNAP = set(A.snap)
TAIL = set(A.tail)

UPM = 1000
U_PER_MM = 560 / A.body_mm     # ช่วงตัวพยัญชนะของแม่แบบ = 560 units
MARK_CX = -280                  # จุดกึ่งกลางเครื่องหมาย (เหนือพยัญชนะก่อนหน้า)
SB = 30                         # side bearing
ASCENT, DESCENT = 1150, -280
VERSION = "1.100"
ASC_BASES = "ปฝฟฬ"             # พยัญชนะหางบน: เลื่อนสระบน/วรรณยุกต์ไปซ้ายให้พ้นหาง
ASC_GAP = 25                    # ช่องว่างขั้นต่ำระหว่างเครื่องหมายกับหาง
TAILED = "ญฐ"                   # มีหางใต้เส้น: เจอสระล่างให้สลับเป็นตัวไม่มีหาง (.notail)
GAP_UP, GAP_LO, GAP_MM = 20, 12, 15   # ช่องว่างแนวตั้งขั้นต่ำ: สระบน/วรรณยุกต์-ตัวอักษร, สระล่าง-ตัวอักษร, วรรณยุกต์-สระบน

UPPER_VOWELS = "ัิีึื็ํ"   # ั ิ ี ึ ื ็ ํ
LOWER_VOWELS = "ุู"                                   # ุ ู
TONES = "่้๊๋์"                        # ่ ้ ๊ ๋ ์
BASES = [chr(c) for c in range(0x0E01, 0x0E2F)]                 # ก..ฮ
BASES += list("ฤฦ")                                    # ฤ ฦ

meta = {m["key"]: m for m in json.load(open(os.path.join(GD, "meta.json"), encoding="utf-8"))}

# ---------- normalize (สำหรับชุดที่เขียนตัวเล็กกว่าแม่แบบ) ----------
def _med(v):
    v = sorted(v)
    return v[len(v)//2] if v else 0.0

_UPM_MM = 560 / A.body_mm
GLOBAL_K = 1.0
Y_SHIFT = {}    # key -> ค่าลบออกจาก y (หน่วยฟอนต์)
if A.scale_to or A.tighten:
    def s_of(m):
        return (_UPM_MM / m["ppm"]) * GLOBAL_K
    cons = [m for m in meta.values() if m["type"] == "base" and len(m["ch"]) == 1
            and 0x0E01 <= ord(m["ch"]) <= 0x0E2E]
    if A.scale_to:
        M0 = _med([m["bbox_h"] * (_UPM_MM / m["ppm"]) for m in cons])
        GLOBAL_K = A.scale_to / M0 if M0 > 0 else 1.0
        print(f"normalize: median cons height {M0:.0f} -> scale x{GLOBAL_K:.3f}")
    if A.tighten:
        tops = lambda ms: [m["base_dy"] * s_of(m) for m in ms]
        bots = lambda ms: [(m["base_dy"] - m["bbox_h"]) * s_of(m) for m in ms]
        def grp(pred):
            return [m for m in meta.values() if len(m["ch"]) == 1 and pred(m)]
        # วางฐานกลุ่มอักษรให้แตะเส้นฐาน (ลบ float ค่ากลางของกลุ่ม)
        groups = {
            "thai": grp(lambda m: m["type"] in ("base",) and (0x0E01 <= ord(m["ch"]) <= 0x0E46 or m["ch"] in "ๅฯ")),
            "lat_up": grp(lambda m: m["ch"].isalpha() and m["ch"].isupper() and ord(m["ch"]) < 128),
            "lat_lo": grp(lambda m: m["ch"].isalpha() and m["ch"].islower() and ord(m["ch"]) < 128),
            "digit": grp(lambda m: m["ch"].isdigit() or 0x0E50 <= ord(m["ch"]) <= 0x0E59),
        }
        drops = {}
        for gname_, ms in groups.items():
            d = max(0.0, _med(bots(ms)))
            drops[gname_] = d
            for m in ms:
                Y_SHIFT[m["key"]] = d
        M = _med(tops(groups["thai"])) - drops["thai"]
        av = [m for m in meta.values() if m["type"] == "upper" and m["ch"] in UPPER_VOWELS]
        tl = [m for m in meta.values() if m["type"] == "upper" and m["ch"] in TONES]
        th = [m for m in meta.values() if m["type"] == "tone2"]
        lo = [m for m in meta.values() if m["type"] == "lower"]
        sh_av = _med(bots(av)) - (M + 35)
        for m in av: Y_SHIFT[m["key"]] = sh_av
        sh_tl = _med(bots(tl)) - (M + 45)
        for m in tl: Y_SHIFT[m["key"]] = sh_tl
        vow_top = _med(tops(av)) - sh_av
        sh_th = _med(bots(th)) - (vow_top + 30)
        for m in th: Y_SHIFT[m["key"]] = sh_th
        sh_lo = _med(tops(lo)) - (-25)
        for m in lo: Y_SHIFT[m["key"]] = sh_lo
        print(f"tighten: M={M:.0f} drops={ {k: round(v) for k, v in drops.items()} } "
              f"av={sh_av:.0f} tl={sh_tl:.0f} th={sh_th:.0f} lo={sh_lo:.0f}")

# ---------- bitmap -> contours ----------
def trace(mask):
    """คืน list ของ loops [(x,y)...] พิกัด px (y ลง)"""
    h, w = mask.shape
    edges = {}   # start -> list of ends
    def add(a, b):
        edges.setdefault(a, []).append(b)
    for r in range(h):
        for c in range(w):
            if not mask[r, c]:
                continue
            if r == 0 or not mask[r-1, c]: add((c, r), (c+1, r))
            if c == w-1 or not mask[r, c+1]: add((c+1, r), (c+1, r+1))
            if r == h-1 or not mask[r+1, c]: add((c+1, r+1), (c, r+1))
            if c == 0 or not mask[r, c-1]: add((c, r+1), (c, r))
    used = set()
    loops = []
    for start in list(edges):
        for end in edges[start]:
            if (start, end) in used:
                continue
            loop = [start]
            a, b = start, end
            used.add((a, b))
            while b != start:
                loop.append(b)
                dx, dy = b[0]-a[0], b[1]-a[1]
                prefs = [(dy, -dx), (dx, dy), (-dy, dx)]
                nxt = None
                for (px, py) in prefs:
                    cand = (b[0]+px, b[1]+py)
                    if cand in [e for e in edges.get(b, [])] and (b, cand) not in used:
                        nxt = cand; break
                if nxt is None:
                    break
                used.add((b, nxt))
                a, b = b, nxt
            if len(loop) >= 4 and b == start:
                loops.append(loop)
    return loops

def shoelace(pts):
    s = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]; x2, y2 = pts[(i+1) % len(pts)]
        s += x1*y2 - x2*y1
    return s / 2.0

def collinear_merge(pts):
    out = []
    n = len(pts)
    for i in range(n):
        p0, p1, p2 = pts[i-1], pts[i], pts[(i+1) % n]
        if (p1[0]-p0[0], p1[1]-p0[1]) != (p2[0]-p1[0], p2[1]-p1[1]):
            out.append(p1)
    return out or pts

def rdp(pts, eps):
    """closed-loop RDP: เปิดลูปที่จุดไกลสุดสองจุด"""
    if len(pts) < 6:
        return pts
    def rdp_open(p):
        if len(p) < 3:
            return p
        ax, ay = p[0]; bx, by = p[-1]
        dmax, idx = -1.0, 0
        dx, dy = bx-ax, by-ay
        L = math.hypot(dx, dy) or 1e-9
        for i in range(1, len(p)-1):
            d = abs(dy*(p[i][0]-ax) - dx*(p[i][1]-ay)) / L
            if d > dmax:
                dmax, idx = d, i
        if dmax > eps:
            l = rdp_open(p[:idx+1]); r = rdp_open(p[idx:])
            return l[:-1] + r
        return [p[0], p[-1]]
    # หมุนลูปให้เริ่มที่จุดไกลสุดจาก centroid
    cx = sum(p[0] for p in pts)/len(pts); cy = sum(p[1] for p in pts)/len(pts)
    k = max(range(len(pts)), key=lambda i: (pts[i][0]-cx)**2 + (pts[i][1]-cy)**2)
    pts = pts[k:] + pts[:k]
    half = len(pts)//2
    a = rdp_open(pts[:half+1]); b = rdp_open(pts[half:] + [pts[0]])
    return a[:-1] + b[:-1]

def load_mask(key):
    return np.asarray(Image.open(os.path.join(GD, key + ".png"))) > 127

def split_tail(mask):
    """แยกหางใต้ตัวของ ญ ฐ -> (ขอบก้นของตัวเป็นแถว px, mask เฉพาะตัวไม่มีหาง)
    หางเป็นชิ้นแยก: หางคือชิ้นที่ก้นต่ำสุดและเริ่มในครึ่งล่าง / หางต่อกับตัว: ตัดที่แถวหมึกบางสุดช่วง 45–95%"""
    h = mask.shape[0]
    img = Image.fromarray(np.where(mask, 255, 0).astype("uint8")).copy()   # copy: fromarray ได้ภาพแบบอ่านอย่างเดียว floodfill ไม่ติด
    comps = []                                   # (label, แถวบน, แถวล่าง, พื้นที่)
    for label in range(1, 250):
        left = np.argwhere(np.asarray(img) == 255)
        if not len(left):
            break
        ImageDraw.floodfill(img, (int(left[0][1]), int(left[0][0])), label)
        rows = np.nonzero(np.asarray(img) == label)[0]
        comps.append((label, int(rows.min()), int(rows.max()), len(rows)))
    lab = np.asarray(img)
    big = [c for c in comps if c[3] >= max(60, 0.01 * mask.sum())]
    tails = [c for c in big if c[1] > 0.45 * h]
    if len(big) >= 2 and tails:
        tail = max(tails, key=lambda c: c[2])
        return max(c[2] for c in big if c[0] != tail[0]) + 1, mask & (lab != tail[0])
    ink = mask.sum(1)
    lo, hi = int(h * 0.45), int(h * 0.95)
    cut = lo + int(np.argmin(ink[lo:hi]))
    body = mask.copy()
    body[cut:, :] = False
    return cut, body

def glyph_contours(mask):
    loops = trace(mask)
    out = []
    for lp in loops:
        if abs(shoelace(lp)) < 150:     # ตัดรูเข็ม/เศษ
            continue
        lp = collinear_merge(lp)
        lp = rdp(lp, 2.0)
        if len(lp) >= 3:
            out.append(lp)
    return out

def to_pen(pen, loops, scale, x_off_px, base_dy, x_unit_off, y_shift=0.0):
    """แปลง loops px -> พิกัดฟอนต์แล้วเขียนลง pen (จุดแหลม=on-curve ที่เหลือ off-curve)"""
    for lp in loops:
        pts = [((p[0] - x_off_px) * scale + x_unit_off,
                (base_dy - p[1]) * scale - y_shift) for p in lp]
        pts = [(round(x), round(y)) for x, y in pts]
        n = len(pts)
        oncurve = []
        for i in range(n):
            ax, ay = pts[i-1]; bx, by = pts[i]; cx2, cy2 = pts[(i+1) % n]
            v1 = (ax-bx, ay-by); v2 = (cx2-bx, cy2-by)
            l1 = math.hypot(*v1) or 1e-9; l2 = math.hypot(*v2) or 1e-9
            cosang = (v1[0]*v2[0] + v1[1]*v2[1]) / (l1*l2)
            oncurve.append(cosang > -0.17)   # มุม < ~100° = แหลม = on-curve
        if not any(oncurve):
            pen.qCurveTo(*pts, None)
            pen.closePath()
            continue
        s = oncurve.index(True)
        order = list(range(s, n)) + list(range(0, s))
        pen.moveTo(pts[s])
        seg = []
        for j in order[1:] + [s]:
            if oncurve[j]:
                if seg:
                    pen.qCurveTo(*seg, pts[j])
                else:
                    pen.lineTo(pts[j])
                seg = []
            else:
                seg.append(pts[j])
        pen.closePath()

# ---------- สร้าง glyphs ----------
glyphs, metrics, cmap = {}, {}, {}
order = [".notdef", "space"]

pen = TTGlyphPen(None)
pen.moveTo((80, 0)); pen.lineTo((80, 640)); pen.lineTo((420, 640)); pen.lineTo((420, 0)); pen.closePath()
pen.moveTo((140, 60)); pen.lineTo((360, 60)); pen.lineTo((360, 580)); pen.lineTo((140, 580)); pen.closePath()
glyphs[".notdef"] = pen.glyph(); metrics[".notdef"] = (500, 80)
pen = TTGlyphPen(None)
glyphs["space"] = pen.glyph(); metrics["space"] = (260, 0)
cmap[0x20] = "space"; cmap[0xA0] = "space"

def gname(ch, high=False):
    return "uni%04X" % ord(ch) + (".high" if high else "")

mark_set = set(UPPER_VOWELS + LOWER_VOWELS + TONES)
built = {}

def build_one(key, ch, high, notail=False):
    m = meta[key]
    scale = U_PER_MM / m["ppm"] * GLOBAL_K
    full = load_mask(key)
    loops = glyph_contours(full)
    if not loops:
        return None
    name = gname(ch, high) + (".notail" if notail else "")
    pen = TTGlyphPen(None)
    is_mark = ch in mark_set
    base_dy = m["base_dy"]
    y_shift = Y_SHIFT.get(key, 0.0)
    if ch in TAIL and not high:
        cut, _ = split_tail(full)
        y_shift = (base_dy - cut) * scale      # ก้นตัวอยู่บนเส้นฐาน หางห้อยลงใต้เส้นแบบตัวพิมพ์
    elif ch in SNAP:
        maxpy = max(p[1] for lp in loops for p in lp)
        if maxpy > base_dy:
            base_dy = maxpy   # ยกทั้งตัวให้ก้นแตะเส้นฐานพอดี
        y_shift = 0.0
    # bbox_w ใน meta นับเศษหมึกที่ trace ทิ้งไปแล้วด้วย -> ตัวเยื้อง/ช่องไฟเกิน (Slim: ้ ี ถ G)
    # ถ้าขอบหมึกจริงต่างจาก meta ชัดเจน ให้ใช้ขอบหมึกจริงแทน
    xs = [p[0] for lp in loops for p in lp]
    ink_x0, ink_w = 0.0, float(m["bbox_w"])
    if abs((max(xs) - min(xs)) - m["bbox_w"]) > max(4, 0.05 * m["bbox_w"]):
        ink_x0, ink_w = float(min(xs)), float(max(xs) - min(xs))
        print(f"  ตัดเศษหมึก: {key} {ch} กว้าง {m['bbox_w']} -> {ink_w:.0f} px")
    if is_mark:
        x_off = ink_x0 + ink_w / 2.0
        x_unit = MARK_CX
        adv = 0
    else:
        x_off = ink_x0
        x_unit = SB
        adv = int(round(ink_w * scale)) + 2 * SB
    if notail:                                  # ตัวเดิมตำแหน่งเดิม ช่องไฟเดิม แค่ไม่มีหาง
        loops = glyph_contours(split_tail(full)[1])
    to_pen(pen, loops, scale, x_off, base_dy, x_unit, y_shift)
    g = pen.glyph()
    glyphs[name] = g
    g.recalcBounds(None)
    lsb = g.xMin if g.numberOfContours else 0
    metrics[name] = (adv, lsb)
    if not high and not notail:
        cmap[ord(ch)] = name
    order.append(name)
    built[name] = {"adv": adv, "mark": is_mark}
    return name

KEY_OF = {}
for key, m in sorted(meta.items()):
    if m["type"] == "spare":
        continue
    ch = m["ch"]
    if ch == "&amp;":
        ch = "&"
    if len(ch) != 1:
        print("skip multi-char:", key, ch); continue
    if build_one(key, ch, high=(m["type"] == "tone2")) and m["type"] == "base":
        KEY_OF[ch] = key

# ญ ฐ ไม่มีหาง: ใช้ตอนมีสระล่าง (ญุ ฐู) ไม่ให้หางชนสระ
for ch in TAILED:
    if ch in KEY_OF:
        build_one(KEY_OF[ch], ch, high=False, notail=True)

# ช่องสำรองที่เขียนซ่อม
for part in A.spare.split(","):
    part = part.strip()
    if part and "=" in part:
        key, ch = part.split("=", 1)
        if key in meta:
            meta[key]["ch"] = ch
            build_one(key, ch, high=False)

# ---------- เครื่องหมายที่ Word ใส่ให้เองตอนพิมพ์ (“ ” ‘ ’ … – —) ----------
# ไม่มีในแม่แบบ -> ประกอบจากเส้นลายมือที่มีอยู่ ไม่งั้น Word จะดึงฟอนต์อื่นมาแทนกลางประโยค
def derive(uni, parts, adv):
    """parts = [(ชื่อ glyph ต้นทาง, transform 6 ค่า)] -> glyph เส้นจริงตัวใหม่"""
    if uni in cmap or any(src not in built for src, _ in parts):
        return
    pen = TTGlyphPen(None)
    for src, tr in parts:
        glyphs[src].draw(TransformPen(pen, tr), None)
    g = pen.glyph()
    g.recalcBounds(None)
    name = "uni%04X" % uni
    glyphs[name] = g
    adv = int(round(adv))
    metrics[name] = (adv, g.xMin if g.numberOfContours else 0)
    cmap[uni] = name
    order.append(name)
    built[name] = {"adv": adv, "mark": False}

ID = (1, 0, 0, 1, 0, 0)
Q1, Q2, DOT, HY = gname("'"), gname('"'), gname("."), gname("-")
for u in (0x2018, 0x2019):
    if Q1 in built: derive(u, [(Q1, ID)], built[Q1]["adv"])
for u in (0x201C, 0x201D):
    if Q2 in built: derive(u, [(Q2, ID)], built[Q2]["adv"])
if DOT in built:
    step = built[DOT]["adv"] - SB
    derive(0x2026, [(DOT, (1, 0, 0, 1, i * step, 0)) for i in range(3)], 2 * step + built[DOT]["adv"])
if HY in built:
    hw = max(1, built[HY]["adv"] - 2 * SB)          # ความยาวเส้นขีดจริง
    for u, target, lo, hi in ((0x2013, 480, 1.0, 3.0), (0x2014, 900, 1.5, 5.0)):
        sx = min(hi, max(lo, target / hw))
        derive(u, [(HY, (sx, 0, 0, 1, SB - SB * sx, 0))], hw * sx + 2 * SB)

print(f"glyphs: {len(order)}")
missing = [c for c in (BASES + list("ะาำเแโใไๅฯๆ฿" ) + list(UPPER_VOWELS+LOWER_VOWELS+TONES)) if ord(c) not in cmap]
print("missing:", [f"{c} U+{ord(c):04X}" for c in missing])

# ---------- จุดยึดเครื่องหมายรายคู่: หลบหาง ป ฝ ฟ ฬ + ยก/กดไม่ให้ชนตัวอักษร ----------
# เดิมทุกคู่ใช้จุดเดียวกัน (กึ่งกลาง, y=0) -> ลายมือที่หัวสูงไม่เท่ากันทำให้ ก็ อื่น ขึ้น ถึง สระจมหัวตัวอักษร
# ตอนนี้วัดขอบหมึกจริงของแต่ละคู่ แล้วยกสระบน/วรรณยุกต์ขึ้น (หรือกดสระล่างลง) เท่าที่ขาดระยะ
from fontTools.pens.basePen import BasePen

class _Flat(BasePen):
    """แตกเส้นโค้งเป็นเส้นตรงสั้น ๆ เก็บเป็นขอบ (x0, y0, x1, y1)"""
    def __init__(self):
        super().__init__(None)
        self.segs, self.p, self.start = [], None, None
    def _moveTo(self, p):
        self.p = self.start = p
    def _lineTo(self, p):
        self.segs.append((*self.p, *p))
        self.p = p
    def _qCurveToOne(self, p1, p2):
        p0 = self.p
        for i in range(1, 7):
            t = i / 6
            self._lineTo(((1-t)**2*p0[0] + 2*(1-t)*t*p1[0] + t*t*p2[0],
                          (1-t)**2*p0[1] + 2*(1-t)*t*p1[1] + t*t*p2[1]))
    def _curveToOne(self, p1, p2, p3):
        self._lineTo(p3)
    def _closePath(self):
        if self.p != self.start:
            self._lineTo(self.start)

STEP = 4
_prof = {}
def profile(n):
    """ขอบล่าง/บนของหมึกทีละคอลัมน์ (ทุก STEP units) -> {คอลัมน์: (y ต่ำสุด, y สูงสุด)}"""
    if n not in _prof:
        pen = _Flat()
        glyphs[n].draw(pen, None)
        cols = {}
        for x0, y0, x1, y1 in pen.segs:
            if x0 == x1:
                continue
            if x0 > x1:
                x0, y0, x1, y1 = x1, y1, x0, y0
            for c in range(math.ceil(x0 / STEP), math.floor(x1 / STEP) + 1):
                y = y0 + (c * STEP - x0) * (y1 - y0) / (x1 - x0)
                lo, hi = cols.get(c, (y, y))
                cols[c] = (min(lo, y), max(hi, y))
        _prof[n] = cols
    return _prof[n]

def clearance(lo_n, lo_dx, up_n, up_dx):
    """ระยะแนวตั้งที่แคบที่สุด ระหว่างขอบบนของ lo กับขอบล่างของ up (เผื่อซ้ายขวา ±2 คอลัมน์)
    None = สองตัวไม่ซ้อนกันในแนวนอนเลย"""
    lo, up = profile(lo_n), profile(up_n)
    worst = None
    for c, (ulo, _) in up.items():
        j = round((c * STEP + up_dx - lo_dx) / STEP)
        tops = [lo[i][1] for i in range(j - 2, j + 3) if i in lo]
        if tops:
            d = ulo - max(tops)
            worst = d if worst is None else min(worst, d)
    return worst

def lift(c, gap):
    return 0 if c is None or c >= gap else int(math.ceil(gap - c))

ASC_NAMES = {gname(c) for c in ASC_BASES}
def top_x(base, ax, mark):
    """จุดยึดแนวนอนของเครื่องหมายบนตัว base: ปกติกึ่งกลาง / ป ฝ ฟ ฬ เลื่อนซ้ายจนขอบขวาพ้นหาง"""
    mg, bg = glyphs[mark], glyphs[base]
    if base not in ASC_NAMES or not mg.numberOfContours or not bg.numberOfContours:
        return ax
    adv = built[base]["adv"]
    # จุดของหางที่สูงถึงระดับเครื่องหมายตัวนี้ (ดูเฉพาะซีกขวา หางของ ป ฝ ฟ ฬ อยู่ขวาเสมอ)
    tail = [x for x, y in bg.coordinates if y >= mg.yMin - ASC_GAP and x > adv * 0.45]
    if not tail:
        return ax
    right = mg.xMax - MARK_CX                      # ความกว้างเครื่องหมายฝั่งขวาของจุดยึด
    return int(max(SB, min(ax, min(tail) - ASC_GAP - right)))

# เครื่องหมายแยกคลาสทีละตัว เพราะแต่ละคู่ (ตัวอักษร, เครื่องหมาย) ได้จุดยึดของตัวเอง
TOP = [gname(c) for c in UPPER_VOWELS + TONES if gname(c) in glyphs]
TOP += [gname(c, True) for c in TONES if gname(c, True) in glyphs]
BOT = [gname(c) for c in LOWER_VOWELS if gname(c) in glyphs]
UPV_N = [gname(c) for c in UPPER_VOWELS if gname(c) in glyphs]
TNH_N = [gname(c, True) for c in TONES if gname(c, True) in glyphs]
MARK_BASES = [n for n in dict.fromkeys([gname(c) for c in BASES + list("ำ")] +
                                       [gname(c) + ".notail" for c in TAILED]) if n in glyphs]
ANCH = {}      # (ตัวอักษร, เครื่องหมาย) -> (x, y)
for b in MARK_BASES:
    ax = built[b]["adv"] // 2
    for t in TOP:
        x = top_x(b, ax, t)
        ANCH[b, t] = (x, lift(clearance(b, 0, t, x - MARK_CX), GAP_UP))
    for lv in BOT:
        ANCH[b, lv] = (ax, -lift(clearance(lv, ax - MARK_CX, b, 0), GAP_LO))
MKMK = {(v, t): lift(clearance(v, 0, t, 0), GAP_MM) for v in UPV_N for t in TOP}   # วรรณยุกต์บนสระบน
moved = sorted({b for (b, t), (x, y) in ANCH.items() if y})
print(f"ยก/กดเครื่องหมายเลี่ยงการชน: {sum(1 for v in ANCH.values() if v[1])} คู่ บน {len(moved)} ตัวอักษร"
      f" | วรรณยุกต์บนสระ {sum(1 for v in MKMK.values() if v)} คู่")

# ---------- FontBuilder ----------
# Windows (Word ฯลฯ) ตัดทุกอย่างที่เกิน usWinAscent/usWinDescent ทิ้ง -> ต้องครอบตัวที่สูง/ลึกที่สุดจริง
# รวมเครื่องหมายที่ถูกยก/กด และวรรณยุกต์ที่ซ้อนบนสระบนด้วย
# นับเฉพาะคู่ที่เกิดจริงตอนแสดงผล ไม่งั้นระยะบรรทัดใน Word ห่างเกินเหตุ: ไม่นับวรรณยุกต์ตัวสูงเกาะพยัญชนะตรง ๆ,
# เครื่องหมายบน ำ ฤ ฦ, และสระล่างใต้ ฎ ฏ (แทบไม่มีในคำจริง) / ญ ฐ ตัวมีหาง (ถูกสลับเป็น .notail ก่อนแล้ว)
_REAL = [n for n in MARK_BASES if n not in {gname(c) for c in "ำฤฦ"}]
_NO_LOW = {gname(c) for c in "ฎฏ" + TAILED}
_tops = [glyphs[n].yMax for n in built if glyphs[n].numberOfContours > 0]
_bots = [glyphs[n].yMin for n in built if glyphs[n].numberOfContours > 0]
for b in _REAL:
    _tops += [glyphs[t].yMax + ANCH[b, t][1] for t in TOP if t not in TNH_N]
    _tops += [glyphs[t].yMax + ANCH[b, v][1] + MKMK[v, t] for v in UPV_N for t in TNH_N]
    if b not in _NO_LOW:
        _bots += [glyphs[lv].yMin + ANCH[b, lv][1] for lv in BOT]
WIN_ASC = max(ASCENT, int(max(_tops)) + 15)
WIN_DESC = max(-DESCENT, int(-min(_bots)) + 15)

fb = FontBuilder(UPM, isTTF=True)
fb.updateHead(fontRevision=float(VERSION))
fb.setupGlyphOrder(order)
fb.setupCharacterMap(cmap)
fb.setupGlyf(glyphs)
fb.setupHorizontalMetrics(metrics)
fb.setupHorizontalHeader(ascent=WIN_ASC, descent=-WIN_DESC)
ps = A.family.replace(" ", "") + "-Regular"
fb.setupNameTable({
    "familyName": A.family,
    "styleName": "Regular",
    "uniqueFontIdentifier": ps + "-" + VERSION,
    "fullName": A.family + " Regular",
    "psName": ps,
    "version": "Version " + VERSION,
    "copyright": "Copyright 2026 Gift (Netthip). Handwriting font.",
})
fb.setupOS2(sTypoAscender=ASCENT, sTypoDescender=DESCENT, sTypoLineGap=120,
            usWinAscent=WIN_ASC, usWinDescent=WIN_DESC,
            achVendID="GIFT",
            fsType=0,                                 # ค่าเดิม 4 = ฝังได้แค่ดู/พิมพ์ -> Canva/Word ฝังฟอนต์ติดปัญหา
            fsSelection=0x40,                         # REGULAR
            ulCodePageRange1=(1 << 0) | (1 << 16))    # Latin-1 + Thai (874): ถ้าเป็น 0 Word ไม่ยอมใช้ฟอนต์เลย (ทดสอบแล้ว ขึ้น Arial แทน)
fb.setupPost()

# ---------- OpenType features ----------
def cls(chars, high=False):
    return " ".join(gname(c, high) for c in chars if gname(c, high) in glyphs)

# ประกาศสคริปต์ thai/latn ไว้ด้วย: มีแค่ DFLT แล้ว HarfBuzz ยังใช้ได้ แต่เอนจินของ Microsoft/Apple ไม่รับประกัน
fea = ["languagesystem DFLT dflt;", "languagesystem thai dflt;", "languagesystem latn dflt;"]
fea.append(f"@BASES = [{cls([c for c in BASES if ord(c) in cmap])}];")
def mcls(n):
    return "@M_" + n.replace(".", "_")
for n in TOP + BOT:
    fea.append(f"markClass [{n}] <anchor {MARK_CX} 0> {mcls(n)};")

# GSUB: วรรณยุกต์หลังสระบน -> ตัวตำแหน่งสูง / ญ ฐ ที่มีสระล่าง -> ตัวไม่มีหาง
fea.append(f"@UPV = [{cls(UPPER_VOWELS)}];")
fea.append(f"@TN = [{cls(TONES)}];")
fea.append(f"@TNH = [{cls(TONES, True)}];")
ccmp = ["feature ccmp {", "  sub @UPV @TN' by @TNH;"]
tailed = [gname(c) for c in TAILED if gname(c) + ".notail" in glyphs]
if tailed and BOT:
    src_ = " ".join(tailed)
    dst_ = " ".join(n + ".notail" for n in tailed)
    ccmp.append(f"  sub [{src_}]' [{' '.join(BOT)}] by [{dst_}];")
ccmp.append("} ccmp;")
fea += ccmp

# GPOS mark-to-base: จุดยึดรายคู่ที่คำนวณไว้ข้างบน
mk = ["feature mark {"]
for b in MARK_BASES:
    parts = " ".join(f"<anchor {ANCH[b, t][0]} {ANCH[b, t][1]}> mark {mcls(t)}" for t in TOP + BOT)
    mk.append(f"  pos base {b} {parts};")
mk.append("} mark;")
fea += mk

# GPOS mark-to-mark (วรรณยุกต์เกาะเหนือสระบน)
mm = ["feature mkmk {"]
for v in UPV_N:
    parts = " ".join(f"<anchor {MARK_CX} {MKMK[v, t]}> mark {mcls(t)}" for t in TOP)
    mm.append(f"  pos mark {v} {parts};")
mm.append("} mkmk;")
fea += mm

# GDEF: จำแนก base/mark ให้เอนจินเรนเดอร์ยอมใช้ GPOS
mark_names = [n for n in order if n in built and built[n]["mark"]]
base_names = [n for n in order if n in built and not built[n]["mark"]]
fea.append("table GDEF { GlyphClassDef [%s], , [%s], ; } GDEF;"
           % (" ".join(base_names), " ".join(mark_names)))

fea_text = "\n".join(fea)
if A.dump_fea:
    open(os.path.join(SCRATCH, A.dump_fea), "w", encoding="utf-8").write(fea_text)
addOpenTypeFeaturesFromString(fb.font, fea_text)

fb.save(OUT_TTF)
print(f"win ascent/descent: {WIN_ASC}/{WIN_DESC}")
print("saved:", OUT_TTF, os.path.getsize(OUT_TTF), "bytes")

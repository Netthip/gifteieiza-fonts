# -*- coding: utf-8 -*-
"""ตัดตัวอักษรลายมือจากสแกนแม่แบบ (สไตล์ A = font any_001..009)"""
import json, os, sys
import numpy as np
from PIL import Image

import argparse
ap = argparse.ArgumentParser()
ap.add_argument("--prefix", default="font any")   # ชื่อไฟล์สแกน <prefix>_001..009.jpg
ap.add_argument("--out", default="glyphs_A")
ap.add_argument("--skip", default="2:ก")          # ช่องที่วงกลมว่าเขียนผิด "page:char,..."
ap.add_argument("--geom", default="geom.json")    # พิกัดช่องของแม่แบบ
ap.add_argument("--baseline-mm", type=float, default=45.0)  # เส้นฐานจากขอบบน writing area
ap.add_argument("--files", default="")            # ระบุไฟล์ตรงๆ "page=path,page=path" (ทับ --prefix)
A = ap.parse_args()

SCRATCH = os.path.dirname(os.path.abspath(__file__))
SRC = r"F:\69"
OUT = os.path.join(SCRATCH, A.out)
os.makedirs(OUT, exist_ok=True)

# หน้าแม่แบบ -> ไฟล์สแกน
if A.files:
    SCANS = {}
    for part in A.files.split(","):
        pg, path = part.split("=", 1)
        SCANS[int(pg)] = path if os.path.isabs(path) else os.path.join(SCRATCH, path)
else:
    SCANS = {p: os.path.join(SRC, f"{A.prefix}_{i:03d}.jpg") for i, p in enumerate(range(2, 11), start=1)}

# จุดอ้างอิงมุมกระดาษ (กึ่งกลางสี่เหลี่ยมดำ 3.5mm ที่ inset 4mm)
FIDS_MM = [(5.75, 5.75), (204.25, 5.75), (5.75, 291.25), (204.25, 291.25)]
BASELINE_MM = A.baseline_mm   # จากขอบบนของ writing area
NOM_PPM = 4961 / 210.0  # ~23.62 px/mm

geom = json.load(open(os.path.join(SCRATCH, A.geom), encoding="utf-8"))

# ช่องที่วงกลมว่าเขียนผิด -> ข้าม (ใช้ช่องสำรองแทน)
SKIP = set()
for part in A.skip.split(","):
    part = part.strip()
    if part and ":" in part:
        pg, ch = part.split(":", 1)
        SKIP.add((int(pg), ch))

def find_fiducial(gray, cx, cy):
    """หาจุดดำใกล้ตำแหน่ง nominal, คืน centroid (x,y) px หรือ None"""
    for r_mm in (7, 12, 18):
        r = int(r_mm * NOM_PPM)
        x0, y0 = int(cx * NOM_PPM) - r, int(cy * NOM_PPM) - r
        x0, y0 = max(x0, 0), max(y0, 0)
        win = gray[y0:y0 + 2 * r, x0:x0 + 2 * r]
        dark = win < 120
        if dark.sum() < 300:
            continue
        ys, xs = np.nonzero(dark)
        return (x0 + xs.mean(), y0 + ys.mean())
    return None

def fit_affine(mm_pts, px_pts):
    """px = A @ mm + t  (least squares)"""
    n = len(mm_pts)
    M = np.zeros((2 * n, 6)); b = np.zeros(2 * n)
    for i, ((mx, my), (px, py)) in enumerate(zip(mm_pts, px_pts)):
        M[2*i] = [mx, my, 1, 0, 0, 0]; b[2*i] = px
        M[2*i+1] = [0, 0, 0, mx, my, 1]; b[2*i+1] = py
    s, *_ = np.linalg.lstsq(M, b, rcond=None)
    return s  # a,b,c,d,e,f : x' = a*x+b*y+c ; y' = d*x+e*y+f

def apply_affine(s, x, y):
    return s[0]*x + s[1]*y + s[2], s[3]*x + s[4]*y + s[5]

def components(ink):
    """connected components (8-conn) บน boolean array, คืน list ของ masks"""
    from collections import deque
    lab = np.zeros(ink.shape, dtype=np.int32)
    cur = 0
    comps = []
    coords = np.argwhere(ink)
    for (r, c) in coords:
        if lab[r, c]:
            continue
        cur += 1
        q = deque([(r, c)]); lab[r, c] = cur
        pix = []
        while q:
            rr, cc = q.popleft(); pix.append((rr, cc))
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    r2, c2 = rr + dr, cc + dc
                    if 0 <= r2 < ink.shape[0] and 0 <= c2 < ink.shape[1] \
                       and not lab[r2, c2] and ink[r2, c2]:
                        lab[r2, c2] = cur; q.append((r2, c2))
        comps.append(pix)
    return comps

meta_all = []
for page, path in SCANS.items():
    img = Image.open(path).convert("RGB")
    arr = np.asarray(img)
    gray = arr.mean(axis=2)
    # affine mm -> px
    px_pts, mm_pts = [], []
    for (mx, my) in FIDS_MM:
        p = find_fiducial(gray, mx, my)
        if p:
            mm_pts.append((mx, my)); px_pts.append(p)
    if len(px_pts) < 3:
        print(f"page {page}: fiducials FAIL ({len(px_pts)})"); continue
    aff = fit_affine(mm_pts, px_pts)
    ppm = float(np.hypot(aff[0], aff[3]))  # px per mm
    cells = [c for c in geom if c["page"] == page]
    n_ok = 0
    for c in cells:
        ch, typ = c["ch"], c["type"]
        if typ == "spare":
            key = f"spare_p{page}"
            i = 1
            while any(m["key"] == f"{key}_{i}" for m in meta_all):
                i += 1
            key = f"{key}_{i}"
        else:
            if ch.startswith("\u25cc"):
                ch = ch[1:]
            if (page, ch) in SKIP:
                continue
            cp = "_".join(f"{ord(x):04X}" for x in ch)
            key = f"u{cp}" + (".high" if typ == "tone2" else "")
        inset = 0.8
        x0m, y0m = c["x"] + inset, c["y"] + inset
        x1m, y1m = c["x"] + c["w"] - inset, c["y"] + c["h"] - inset
        corners = [apply_affine(aff, x, y) for (x, y) in
                   [(x0m, y0m), (x1m, y0m), (x0m, y1m), (x1m, y1m)]]
        xs = [p[0] for p in corners]; ys = [p[1] for p in corners]
        X0, X1 = int(min(xs)), int(max(xs)); Y0, Y1 = int(min(ys)), int(max(ys))
        crop = arr[Y0:Y1, X0:X1].astype(int)
        mx = crop.max(axis=2); mn = crop.min(axis=2)
        lum = crop.mean(axis=2)
        # หมึกดำ = มืดและไม่มีสี หรือมืดจัด (หมึกทับเส้นสีก็เก็บ)
        ink = ((mx < 135) & ((mx - mn) < 55)) | (lum < 95)
        # closing 3x3 อุดรูเข็ม/ขอบขรุขระจาก JPEG
        pad = np.pad(ink, 1)
        dil = np.zeros_like(pad)
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                dil |= np.roll(np.roll(pad, dr, 0), dc, 1)
        ero = np.ones_like(pad)
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                ero &= np.roll(np.roll(dil, dr, 0), dc, 1)
        ink = ero[1:-1, 1:-1]
        comps = components(ink)
        comps = [p for p in comps if len(p) >= 50]
        if not comps:
            if typ != "spare":
                print(f"page {page} '{ch}' ({typ}): EMPTY")
            continue
        mask = np.zeros(ink.shape, dtype=bool)
        for p in comps:
            rr = [q[0] for q in p]; cc = [q[1] for q in p]
            mask[rr, cc] = True
        ys2, xs2 = np.nonzero(mask)
        bx0, bx1, by0, by1 = xs2.min(), xs2.max(), ys2.min(), ys2.max()
        sub = mask[by0:by1 + 1, bx0:bx1 + 1]
        Image.fromarray((sub * 255).astype(np.uint8)).save(os.path.join(OUT, key + ".png"))
        _, base_y = apply_affine(aff, (x0m + x1m) / 2, c["y"] + BASELINE_MM)
        cx_wa_px, _ = apply_affine(aff, (c["x"] + c["w"] / 2), c["y"])
        meta_all.append({
            "key": key, "page": page, "ch": ch, "type": typ,
            "ppm": round(ppm, 4),
            "bbox_w": int(bx1 - bx0 + 1), "bbox_h": int(by1 - by0 + 1),
            "base_dy": round(float(base_y - (Y0 + by0)), 2),   # baseline ต่ำกว่าขอบบน bbox กี่ px
            "cx_off": round(float((X0 + (bx0 + bx1) / 2) - cx_wa_px), 2),  # กึ่งกลาง bbox ห่างกึ่งกลางช่อง
            "ink": len(ys2),
        })
        n_ok += 1
    print(f"page {page}: {n_ok} glyphs, ppm={ppm:.2f}")

json.dump(meta_all, open(os.path.join(OUT, "meta.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(f"total: {len(meta_all)} glyphs -> {OUT}")

# contact sheet เอาไว้ตรวจตา
metas = sorted(meta_all, key=lambda m: (m["page"], m["key"]))
COLS, TH = 14, 72
rows = (len(metas) + COLS - 1) // COLS
sheet = Image.new("L", (COLS * (TH + 8), rows * (TH + 22)), 255)
from PIL import ImageDraw
d = ImageDraw.Draw(sheet)
for i, m in enumerate(metas):
    g = Image.open(os.path.join(OUT, m["key"] + ".png"))
    g.thumbnail((TH, TH))
    cx, cy = (i % COLS) * (TH + 8) + 4, (i // COLS) * (TH + 22) + 2
    sheet.paste(Image.eval(g, lambda v: 255 - v), (cx, cy))
    d.text((cx, cy + TH + 2), m["ch"][:6] if m["type"] != "spare" else m["key"][-8:], fill=0)
sheet.save(os.path.join(OUT, "contact.png"))
print("contact sheet saved")

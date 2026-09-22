# -*- coding: utf-8 -*-
"""สร้างฟอนต์ทั้งตระกูล Gifteieiza ใหม่จาก glyphs/ ของแต่ละโฟลเดอร์ + ทำ specimen.png
ใช้: python tools/rebuild_all.py            (ทุกตัว)
     python tools/rebuild_all.py gifteieiza-soft   (เฉพาะตัวที่ระบุ)
ต้องมี: fonttools pillow numpy uharfbuzz"""
import os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # โฟลเดอร์ fonts/
TOOLS = os.path.join(ROOT, "tools")
# ชุดที่เขียนตัวเล็ก/เขียนหาง ญ ฐ ไว้ในบรรทัด -> normalize + วางหางใต้เส้น
PEN = ["--spare", "", "--tail", "ญฐ", "--scale-to", "545", "--tighten"]
MINI = PEN + ["--body-mm", "14.5"]
JOBS = [
    # โฟลเดอร์, ชื่อฟอนต์, ไฟล์, อาร์กิวเมนต์เพิ่ม
    ("gifteieiza",       "Gifteieiza",       "Gifteieiza-Regular.ttf",       []),   # แม่แบบใหญ่ ใช้ค่าเริ่มต้น
    ("gifteieiza-pen",   "Gifteieiza Pen",   "GifteieizaPen-Regular.ttf",   PEN),
    ("gifteieiza-round", "Gifteieiza Round", "GifteieizaRound-Regular.ttf", MINI),
    ("gifteieiza-slim",  "Gifteieiza Slim",  "GifteieizaSlim-Regular.ttf",  MINI),
    ("gifteieiza-firm",  "Gifteieiza Firm",  "GifteieizaFirm-Regular.ttf",  MINI),
    ("gifteieiza-soft",  "Gifteieiza Soft",  "GifteieizaSoft-Regular.ttf",  MINI),
]

only = set(sys.argv[1:])
fail = 0
for folder, family, ttf, extra in JOBS:
    if only and folder not in only:
        continue
    d = os.path.join(ROOT, folder)
    out = os.path.join(d, ttf)
    cmd = [sys.executable, os.path.join(TOOLS, "build_font.py"), "--glyphs", os.path.join(d, "glyphs"),
           "--family", family, "--out", out] + extra
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(f"== {folder}: {'ok' if r.returncode == 0 else 'FAILED'}")
    print("\n".join(l for l in r.stdout.splitlines() if l.startswith(("win ", "ยก/กด", "missing: ['"))))
    if r.returncode:
        print(r.stderr[-1500:])
        fail += 1
        continue
    s = subprocess.run([sys.executable, os.path.join(TOOLS, "specimen.py"), out, os.path.join(d, "specimen.png")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(s.stdout.strip() or s.stderr[-800:])

# Gifteieiza Blend: รวม 4 สไตล์แม่แบบมินิ -> ต้องทำหลังสร้าง 4 ตัวนั้นเสร็จ
if not fail and (not only or "gifteieiza-blend" in only):
    r = subprocess.run([sys.executable, os.path.join(TOOLS, "blend.py")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(f"== gifteieiza-blend: {'ok' if r.returncode == 0 else 'FAILED'}")
    print("\n".join(l for l in r.stdout.splitlines() if l.startswith(("ตัวอักษร", "win ", "ยก/กด", "missing: ['"))))
    if r.returncode:
        print(r.stderr[-1500:]); fail += 1
    else:
        d = os.path.join(ROOT, "gifteieiza-blend")
        s = subprocess.run([sys.executable, os.path.join(TOOLS, "specimen.py"), os.path.join(d, "GifteieizaBlend-Regular.ttf"),
                            os.path.join(d, "specimen.png")], capture_output=True, text=True, encoding="utf-8", errors="replace")
        print(s.stdout.strip() or s.stderr[-800:])
sys.exit(1 if fail else 0)

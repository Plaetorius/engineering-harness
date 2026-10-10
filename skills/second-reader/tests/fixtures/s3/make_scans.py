#!/usr/bin/env python3
"""Make image-only (scanned) variants of eurotec_textlayer.pdf. Run: uv run --with pillow python make_scans.py
Deterministic (seeded). Variants: scanned_clean.pdf (300 dpi), scanned_poor.pdf (low-res, blur, noise, skew, JPEG)."""
import random, subprocess, tempfile
from pathlib import Path
from PIL import Image, ImageFilter

here = Path(__file__).resolve().parent
src = here / "eurotec_textlayer.pdf"
tmp = Path(tempfile.mkdtemp())
subprocess.run(["pdftoppm", "-r", "300", "-png", "-singlefile", str(src), str(tmp / "p")], check=True)
base = Image.open(tmp / "p.png").convert("L")
base.save(here / "scanned_clean.pdf", "PDF", resolution=300.0)

R = random.Random(11)
img = base.resize((base.width * 55 // 100, base.height * 55 // 100), Image.BILINEAR)     # ~165 dpi
img = img.filter(ImageFilter.GaussianBlur(0.9))
px = img.load()
for _ in range(img.width * img.height // 400):                                           # speckle noise
    x, y = R.randrange(img.width), R.randrange(img.height)
    px[x, y] = R.choice((0, 255, 120))
img = img.rotate(0.4, resample=Image.BICUBIC, fillcolor=255)
img.save(tmp / "poor.jpg", "JPEG", quality=40)
Image.open(tmp / "poor.jpg").save(here / "scanned_poor.pdf", "PDF", resolution=165.0)
print("done")

# a deliberately unreadable scan (heavy noise) for the 'drop and report' path
img2 = base.resize((base.width * 35 // 100, base.height * 35 // 100), Image.BILINEAR).filter(ImageFilter.GaussianBlur(2.2))
px = img2.load()
for _ in range(img2.width * img2.height // 5):
    px[R.randrange(img2.width), R.randrange(img2.height)] = R.choice((0, 255))
img2.save(here / "scanned_unreadable.pdf", "PDF", resolution=105.0)

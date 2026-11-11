# -*- coding: utf-8 -*-
"""生成应用图标 app.ico（多尺寸）"""
import math
from PIL import Image, ImageDraw

S = 2048  # supersampled canvas
CX = S * 0.5


def lerp(a, b, t):
    return a + (b - a) * t


def vgrad(size, c_top, c_bot):
    img = Image.new("RGB", (1, size))
    px = img.load()
    for y in range(size):
        t = y / (size - 1)
        px[0, y] = (
            int(lerp(c_top[0], c_bot[0], t)),
            int(lerp(c_top[1], c_bot[1], t)),
            int(lerp(c_top[2], c_bot[2], t)),
        )
    return img.resize((size, size), Image.BICUBIC)


def qbez(p0, p1, p2, n=48):
    out = []
    for i in range(n + 1):
        t = i / n
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1]
        out.append((x, y))
    return out


# ---------- background: rounded square ----------
bg = vgrad(S, (0x4C, 0x7D, 0xFF), (0x0A, 0x14, 0x2E)).convert("RGBA")
r = int(S * 0.215)
mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=r, fill=255)
bg.putalpha(mask)

# ---------- shield path ----------
y_top = S * 0.180
y_sh = S * 0.520
y_bot = S * 0.880
hw = S * 0.295
cr = S * 0.090

pts = []
pts.append((CX, y_bot))
pts += qbez((CX, y_bot), (CX - hw * 0.97, y_bot - S * 0.115), (CX - hw, y_sh), 40)
pts.append((CX - hw, y_top + cr))
pts += qbez((CX - hw, y_top + cr), (CX - hw, y_top), (CX - hw + cr, y_top), 16)
pts.append((CX + hw - cr, y_top))
pts += qbez((CX + hw - cr, y_top), (CX + hw, y_top), (CX + hw, y_top + cr), 16)
pts.append((CX + hw, y_sh))
pts += qbez((CX + hw, y_sh), (CX + hw * 0.97, y_bot - S * 0.115), (CX, y_bot), 40)

shield = pts
shield_mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(shield_mask).polygon(shield, fill=255)

shield_fill = vgrad(S, (0xFF, 0xFF, 0xFF), (0xDD, 0xE6, 0xFA)).convert("RGBA")
bg.paste(shield_fill, (0, 0), shield_mask)

# ---------- prohibition ring ----------
cx2, cy2 = CX, S * 0.478
ro = S * 0.178
ring_w = int(S * 0.055)
RED = (0xE0, 0x3B, 0x2E, 255)

ring = Image.new("RGBA", (S, S), (0, 0, 0, 0))
rd = ImageDraw.Draw(ring)
rd.ellipse([cx2 - ro, cy2 - ro, cx2 + ro, cy2 + ro], outline=RED, width=ring_w)

# diagonal slash (45deg, upper-left -> lower-right)
ang = math.radians(45)
dx, dy = math.cos(ang), math.sin(ang)
inner = ro - ring_w * 0.55
p1 = (cx2 - dx * inner, cy2 - dy * inner)
p2 = (cx2 + dx * inner, cy2 + dy * inner)
rd.line([p1, p2], fill=RED, width=int(ring_w * 0.92))
# round the slash caps
for p in (p1, p2):
    rr = ring_w * 0.46
    rd.ellipse([p[0] - rr, p[1] - rr, p[0] + rr, p[1] + rr], fill=RED)

bg = Image.alpha_composite(bg, ring)

# ---------- export ----------
sizes = [256, 128, 96, 64, 48, 40, 32, 24, 20, 16]
big = bg.resize((256, 256), Image.LANCZOS)
big.save("app.ico", format="ICO", sizes=[(s, s) for s in sizes])
big.save("icon_preview.png")
print("app.ico written")

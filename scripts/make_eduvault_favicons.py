"""Generate the EduVault favicon set (rebrand 2026-07-11, plan vast-hopping-sketch).

Renders a minimal "E" monogram — rounded square in brand pink #C82E6E with a
white Montserrat-Bold letter — and writes the full favicon set consumed by
frontend/index.html:

    frontend/public/brand/favicon-{16,32,48,180,192,512}.png
    frontend/public/brand/favicon.ico
    frontend/public/favicon.ico

It also OVERWRITES logo.png / logo-transparent.png / logo-mark.png with the
same monogram so no stale CFP logo can ever be served from /brand/* (the app
components no longer reference them, but hotlinks/bookmarks might).

Font: pass the path to a Montserrat TTF (variable or static) as argv[1];
falls back to Arial Bold if omitted (Windows).

Run:
    python scripts/make_eduvault_favicons.py [path/to/Montserrat.ttf]
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BRAND_PINK = (0xC8, 0x2E, 0x6E)
BRAND_GREEN = (0x76, 0x9E, 0x2E)
BRAND_DIR = Path("frontend/public/brand")
ROOT_FAVICON = Path("frontend/public/favicon.ico")

BASE = 512  # master render size, downscaled for the rest
SIZES = [16, 32, 48, 180, 192, 512]


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = []
    if len(sys.argv) > 1:
        candidates.append(sys.argv[1])
    candidates += [
        r"C:\Windows\Fonts\arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for cand in candidates:
        try:
            font = ImageFont.truetype(cand, size=size)
            try:  # variable font (Montserrat[wght].ttf): pin Bold
                font.set_variation_by_axes([700])
            except OSError:
                pass
            return font
        except OSError:
            continue
    raise RuntimeError("No usable TTF font found for the monogram")


def make_mark() -> Image.Image:
    img = Image.new("RGBA", (BASE, BASE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    radius = BASE // 5
    draw.rounded_rectangle([0, 0, BASE - 1, BASE - 1], radius=radius, fill=BRAND_PINK)
    # green accent bar at the bottom, echoing the branded image placeholder
    bar_h = BASE // 10
    draw.rounded_rectangle(
        [0, BASE - bar_h - radius, BASE - 1, BASE - 1], radius=radius, fill=BRAND_GREEN
    )
    draw.rectangle([0, BASE - bar_h - radius, BASE - 1, BASE - bar_h], fill=BRAND_PINK)
    font = _load_font(int(BASE * 0.62))
    # optical centre: nudge the glyph up so the accent bar doesn't crowd it
    draw.text(
        (BASE // 2, int(BASE * 0.44)),
        "E",
        font=font,
        fill=(255, 255, 255),
        anchor="mm",
    )
    return img


def main() -> None:
    BRAND_DIR.mkdir(parents=True, exist_ok=True)
    mark = make_mark()

    for size in SIZES:
        out = BRAND_DIR / f"favicon-{size}.png"
        mark.resize((size, size), Image.LANCZOS).save(out)
        print(f"written {out}")

    ico_sizes = [(16, 16), (32, 32), (48, 48)]
    mark.save(BRAND_DIR / "favicon.ico", sizes=ico_sizes)
    mark.save(ROOT_FAVICON, sizes=ico_sizes)
    print(f"written {BRAND_DIR / 'favicon.ico'} and {ROOT_FAVICON}")

    # Neutralise the legacy logo files (no component references them anymore,
    # but stale hotlinks must never resolve to the old CFP artwork).
    for name in ("logo.png", "logo-transparent.png", "logo-mark.png"):
        mark.resize((256, 256), Image.LANCZOS).save(BRAND_DIR / name)
        print(f"written {BRAND_DIR / name}")


if __name__ == "__main__":
    main()

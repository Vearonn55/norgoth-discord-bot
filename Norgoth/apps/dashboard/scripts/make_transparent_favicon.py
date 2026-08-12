"""Regenerate dashboard favicon assets with a transparent background.

Treats near-pure black background pixels as transparent while preserving
logo pixels. Source of truth: apps/dashboard/src/app/icon.png (or the
path passed as argv[1]).

Usage:
  python scripts/make_transparent_favicon.py
  python scripts/make_transparent_favicon.py path/to/source.png
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

# Pure / near-black baked into opaque RGB; keep any channel above this.
BLACK_THRESHOLD = 12

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "src" / "app" / "icon.png"
OUT_ICON = ROOT / "src" / "app" / "icon.png"
OUT_APPLE = ROOT / "src" / "app" / "apple-icon.png"
OUT_PUBLIC = ROOT / "public" / "favicon.png"
OUT_ICO = ROOT / "src" / "app" / "favicon.ico"
ICO_SIZES = [(16, 16), (32, 32), (48, 48)]


def make_transparent(src: Image.Image, threshold: int = BLACK_THRESHOLD) -> Image.Image:
    rgba = src.convert("RGBA")
    pixels = list(rgba.getdata())  # Pillow <14; get_flattened_data on 14+
    out = []
    for r, g, b, a in pixels:
        if r <= threshold and g <= threshold and b <= threshold:
            out.append((0, 0, 0, 0))
        else:
            out.append((r, g, b, a))
    rgba.putdata(out)
    return rgba


def main() -> None:
    source_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SOURCE
    if not source_path.is_file():
        raise SystemExit(f"Source PNG not found: {source_path}")

    transparent = make_transparent(Image.open(source_path))
    if transparent.size != (512, 512):
        transparent = transparent.resize((512, 512), Image.Resampling.LANCZOS)

    OUT_ICON.parent.mkdir(parents=True, exist_ok=True)
    OUT_PUBLIC.parent.mkdir(parents=True, exist_ok=True)

    transparent.save(OUT_ICON, format="PNG")
    transparent.save(OUT_APPLE, format="PNG")
    transparent.save(OUT_PUBLIC, format="PNG")

    ico_frames = [
        transparent.resize(size, Image.Resampling.LANCZOS) for size in ICO_SIZES
    ]
    ico_frames[0].save(
        OUT_ICO,
        format="ICO",
        sizes=ICO_SIZES,
        append_images=ico_frames[1:],
    )

    # Quick sanity: at least some fully transparent pixels.
    alpha0 = sum(1 for p in transparent.getdata() if p[3] == 0)
    print(f"Wrote {OUT_ICON}")
    print(f"Wrote {OUT_APPLE}")
    print(f"Wrote {OUT_PUBLIC}")
    print(f"Wrote {OUT_ICO}")
    print(f"Transparent pixels: {alpha0}")


if __name__ == "__main__":
    main()

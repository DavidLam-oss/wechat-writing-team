#!/usr/bin/env python3
"""Render a diagram HTML file to PNG with headless Chrome.

The diagrams in ``assets/`` are generated from the HTML sources in this folder.
No image-generation model is involved: layout is HTML/CSS and the screenshot is
taken by Chrome, so CJK text and version numbers stay pixel-accurate.

Typical use (from the repository root)::

    python3 assets/source/render.py assets/source/writer.html
    python3 assets/source/render.py assets/source/director.html

Output defaults to the input path with a ``.png`` suffix, trimmed of the
trailing uniform background.

Extra options::

    --width 1400            logical CSS width of the viewport (default 1400)
    --tall 1400             provisional viewport height (default 1400)
    --canvas 16:9           letterbox the result onto a 16:9 white canvas
                            (used for the homepage hero, so object-cover
                            crops nothing)
    --webp assets/x.webp --resize 1600x900
                            also export a WebP at the given size

Chrome is located automatically. Set ``CHROME`` to override, e.g.::

    CHROME="/usr/bin/chromium" python3 assets/source/render.py assets/source/writer.html
"""
import argparse
import os
import pathlib
import shutil
import subprocess
import sys

from PIL import Image

CANDIDATES = [
    # macOS
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    # Linux / PATH
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
    # Windows
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]

DSF = 2  # device scale factor: 2x for crisp text


def find_chrome() -> str:
    override = os.environ.get("CHROME")
    if override:
        if pathlib.Path(override).exists() or shutil.which(override):
            return override
        sys.exit(f"CHROME is set to {override!r} but it does not exist / is not executable.")

    for cand in CANDIDATES:
        if os.path.isabs(cand):
            if pathlib.Path(cand).exists():
                return cand
        else:
            found = shutil.which(cand)
            if found:
                return found

    sys.exit(
        "Could not find Chrome/Chromium. Install it, or point the CHROME "
        "environment variable at the binary."
    )


def parse_ratio(text: str):
    try:
        w, h = text.split(":")
        return int(w), int(h)
    except Exception:
        sys.exit(f"Invalid --canvas value {text!r}; expected e.g. 16:9")


def trim_trailing_background(im: Image.Image) -> Image.Image:
    """Crop the image to its last row that differs from the top-left pixel colour."""
    px = im.load()
    w, h = im.size
    bg = px[0, 0]
    last = 0
    for y in range(h - 1, -1, -1):
        for x in range(0, w, 7):
            if px[x, y] != bg:
                last = y
                break
        else:
            continue
        break
    pad = 30 * DSF
    return im.crop((0, 0, w, min(h, last + 1 + pad)))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("html", help="path to the diagram HTML file")
    ap.add_argument("--width", type=int, default=1400, help="logical viewport width (default 1400)")
    ap.add_argument("--tall", type=int, default=1400, help="provisional viewport height (default 1400)")
    ap.add_argument("--canvas", help="letterbox onto this ratio, e.g. 16:9")
    ap.add_argument("--webp", help="also export a WebP to this path")
    ap.add_argument("--resize", help="size for the WebP export, e.g. 1600x900")
    ap.add_argument("--keep-untrimmed", action="store_true", help="skip the background trim")
    args = ap.parse_args()

    chrome = find_chrome()
    src = pathlib.Path(args.html).resolve()
    if not src.exists():
        sys.exit(f"Input HTML not found: {src}")

    out = src.with_suffix(".png")
    cmd = [
        chrome,
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        f"--force-device-scale-factor={DSF}",
        f"--window-size={args.width},{args.tall}",
        f"--screenshot={out}",
        f"file://{src}",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if not out.exists():
        sys.exit(f"Render failed.\nstdout:\n{proc.stdout[-800:]}\nstderr:\n{proc.stderr[-800:]}")

    im = Image.open(out).convert("RGB")
    if not args.keep_untrimmed:
        im = trim_trailing_background(im)

    if args.canvas:
        rw, rh = parse_ratio(args.canvas)
        w, h = im.size
        target_h = round(w * rh / rw)
        if target_h < h:
            sys.exit(f"Content is taller than the {args.canvas} canvas; widen the HTML or drop --canvas.")
        canvas = Image.new("RGB", (w, target_h), (255, 255, 255))
        canvas.paste(im, (0, (target_h - h) // 2))
        im = canvas

    im.save(out)
    print(f"{out.name}: {im.size[0]}x{im.size[1]}")

    if args.webp:
        webp = pathlib.Path(args.webp)
        webp.parent.mkdir(parents=True, exist_ok=True)
        export = im
        if args.resize:
            try:
                ew, eh = (int(v) for v in args.resize.lower().split("x"))
            except Exception:
                sys.exit(f"Invalid --resize value {args.resize!r}; expected e.g. 1600x900")
            export = im.resize((ew, eh), Image.LANCZOS)
        export.save(webp, "WEBP", quality=90, method=6)
        print(f"{webp}: {export.size[0]}x{export.size[1]} ({webp.stat().st_size // 1024}KB)")


if __name__ == "__main__":
    main()

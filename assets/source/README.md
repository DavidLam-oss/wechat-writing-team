# Diagram sources

The workflow diagrams used by the README (and by the project homepage) are generated from
the HTML files in this folder.

## Why HTML instead of an image editor

The charts are dense with Chinese text, version numbers and code identifiers. Hand-drawn or
AI-generated images blur those details. Rendering HTML with headless Chrome keeps every
character pixel-accurate, and editing a caption is a one-line change instead of a redraw.

## Files

| File | Produces | Used by |
|:--|:--|:--|
| `writer.html` | `assets/wechat_writer_flow_wide_clean_v37.png` | README — WeChat Writer pipeline |
| `director.html` | `assets/wechat_director_flow_wide_clean_v251.png` | README — WeChat Director pipeline |

The homepage hero (`xiaoweibox-mono/apps/home/public/project-writing-team.webp`) is the same
`writer.html` output, letterboxed onto a 16:9 canvas.

## Rendering

Requires Python 3 with Pillow (`pip install pillow`) and Chrome/Chromium. Run from the
repository root:

```bash
# README diagrams
python3 assets/source/render.py assets/source/writer.html
python3 assets/source/render.py assets/source/director.html

# Homepage hero (16:9, no cropping under object-cover)
python3 assets/source/render.py assets/source/writer.html \
  --canvas 16:9 --webp /tmp/project-writing-team.webp --resize 1600x900
```

Output defaults to the input path with a `.png` suffix, trimmed of trailing blank space.
`--width` / `--tall` control the viewport, `--canvas` letterboxes, `--webp` / `--resize`
export an additional WebP.

Chrome is located automatically (macOS, Linux and Windows paths are tried, plus
`google-chrome` / `chromium` on `PATH`). Override with an environment variable if needed:

```bash
CHROME="/usr/bin/chromium" python3 assets/source/render.py assets/source/writer.html
```

## Keeping the diagrams honest

The text inside each HTML file mirrors the corresponding `SKILL.md`. When a stage name,
persona, version number, output directory or provider order changes in a skill, update the
matching HTML here and re-render — otherwise the published chart starts contradicting the
code. The bodies are plain HTML/CSS with no external assets, so they render identically
offline.

Fonts fall back to the platform's CJK stack. macOS (PingFang SC) gives the closest match to
the committed PNGs; on Linux install `fonts-noto-cjk` for equivalent quality.

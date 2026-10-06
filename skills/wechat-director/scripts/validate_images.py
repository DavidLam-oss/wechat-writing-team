#!/usr/bin/env python3
"""验收 Agent / 平台生成的图片；规格规则统一来自 image_validation.py。

用途：当图片不是由 `visualize.py` 直接生成（例如当前 Agent 自带生图或用平台
工具出图）时，在注入正文、交给 writer 发布之前，用本脚本对照分镜做一次
齐图 + 尺寸 + 比例 + 可读性验收。

用法：
    python3 validate_images.py <项目>/zpicture.assets --brief <项目>/Storyboard.md
"""

import argparse
import json
import sys

if sys.version_info < (3, 10):
    print("Python 3.10+ is required for image validation.", file=sys.stderr)
    raise SystemExit(2)

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from console_encoding import configure_console

configure_console()

from image_validation import validate_directory


def expected_stems(brief_path):
    """按 visualize.py 的命名规则推导期望的图片文件名主干。

    - 封面（cover-*）：`{suffix}`，例如 cover-main / cover-sidebar
    - 内文配图：`{title}-{suffix}`，例如 标题-illustration-01（同时兼容无前缀写法）
    """
    from brief_parser import parse_visual_brief

    title, tasks = parse_visual_brief(Path(brief_path))
    stems = []
    for task in tasks:
        suffix = task["suffix"]
        if suffix.startswith("cover"):
            stems.append(suffix)
        else:
            stems.append(f"{title}-{suffix}")
    stems.append("cover-combined")  # stitch_covers 产出的合成封面
    return title, stems


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", help="项目 zpicture.assets/ 目录")
    parser.add_argument("--allow-empty", action="store_true", help="允许目录没有可识别图片")
    parser.add_argument("--brief", help="Storyboard.md；完整验收时必传，用于检查缺图")
    args = parser.parse_args()

    expected = None
    if args.brief:
        try:
            _, expected = expected_stems(args.brief)
        except Exception as exc:  # noqa: BLE001 - 作为验收失败上报
            print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False))
            return 2
        if not any(not stem.startswith("cover") for stem in expected):
            print(json.dumps({"valid": False, "error": "no storyboard tasks"}, ensure_ascii=False))
            return 1

    result = validate_directory(args.directory,
                               require_assets=not args.allow_empty,
                               expected_files=expected)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("valid") else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""图片交付规格的单一事实来源（WeChat Director）。

尺寸与比例直接取自 `director_core.ASPECT_RATIOS`，避免生图脚本与验收脚本
各写一份规格、日后再打架。本模块不做任何生成或上传动作，只做只读校验。
"""

import sys
from pathlib import Path

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from director_core import ASPECT_RATIOS

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None

PROFILE = "wechat_default"
SUPPORTED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
# 允许的比例偏差（不同模型输出会有轻微取整差异）
RATIO_TOLERANCE = 0.08

# 分类关键词 -> ASPECT_RATIOS 中的 kind（长关键词在前，避免 "cover-main" 被 "cover" 抢先）
_CLASSIFY_ORDER = ("cover-combined", "cover-main", "cover-sidebar", "illustration", "quote")


def requirements():
    """各类型图片的最低尺寸要求，例如 {"cover-main": (1504, 640), ...}。"""
    return {kind: (dims["width"], dims["height"]) for kind, dims in ASPECT_RATIOS.items()}


def classify_image(name):
    """按文件名子串判断图片类型；无法归类返回 None。

    兼容 `cover-main.jpg` 与 `标题-illustration-01.jpg` 两种命名。
    """
    lowered = name.lower()
    for kind in _CLASSIFY_ORDER:
        if kind in lowered:
            return kind
    return None


def read_image_size(path):
    """返回 (width, height)；失败时返回 (None, 错误信息)。"""
    if Image is None:
        return None, "Pillow is not installed"
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            return image.size, None
    except Exception as exc:  # noqa: BLE001 - 交给调用方展示
        return None, str(exc)


def validate_image(path, kind=None):
    """校验单张图片：可读、尺寸达标、比例正确。"""
    path = Path(path)
    kind = classify_image(kind or path.name)
    if not kind:
        return {"status": "ignored", "file": str(path)}

    required = requirements().get(kind)
    result = {"file": str(path), "kind": kind}
    if required is None:
        # 如 cover-combined：由脚本拼接产出，尺寸依赖侧边栏高度，不做硬性规格校验
        size, error = read_image_size(path)
        if error:
            result.update(status="unreadable", error=error)
            return result
        result.update(status="ok", actual=list(size), required=None)
        return result

    result["required"] = list(required)
    size, error = read_image_size(path)
    if error:
        result.update(status="unreadable", error=error)
        return result

    width, height = size
    result["actual"] = [width, height]
    if width < required[0] or height < required[1]:
        result["status"] = "too_small"
    elif abs((width / height) - (required[0] / required[1])) > RATIO_TOLERANCE:
        result["status"] = "wrong_ratio"
        result["expected_ratio"] = round(required[0] / required[1], 3)
    else:
        result["status"] = "ok"
    return result


def validate_directory(directory, require_assets=True, expected_files=None):
    """校验一个图片目录（通常是项目 `zpicture.assets/`）。

    expected_files: 期望存在的文件名主干（不含扩展名）；缺图会体现在 missing。
    """
    directory = Path(directory)
    if not directory.is_dir():
        return {"valid": False, "error": f"image directory not found: {directory}",
                "files": [], "missing": sorted(expected_files or []), "unsupported": []}

    all_paths = [p for p in sorted(directory.iterdir()) if p.is_file()]
    stems = {p.stem for p in all_paths if p.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES}
    missing = sorted(set(expected_files or []) - stems)

    classified = [p for p in all_paths if classify_image(p.name)]
    unsupported = sorted(
        p.name for p in classified if p.suffix.lower() not in SUPPORTED_IMAGE_SUFFIXES
    )
    paths = [p for p in classified if p.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES]
    if expected_files:
        paths = [p for p in paths if p.stem in set(expected_files)]

    if require_assets and not paths:
        return {"valid": False, "error": "no classified image assets found",
                "files": [], "missing": missing, "unsupported": unsupported}

    files = [validate_image(path) for path in paths]
    return {
        "valid": not missing and not unsupported
                 and all(item["status"] == "ok" for item in files),
        "profile": PROFILE,
        "files": files,
        "missing": missing,
        "unsupported": unsupported,
    }

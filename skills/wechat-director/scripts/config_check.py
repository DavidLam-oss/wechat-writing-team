#!/usr/bin/env python3
"""
config_check.py - WeChat Director 配置检测
首次使用 /draw 前运行，检查生图环境是否就绪。

返回状态:
  0 - 环境就绪（可能有可选能力缺失，不影响基础流程）
  1 - 关键脚本缺失
  2 - Python 版本不满足
"""

import argparse
import json
import shutil
import sys

if sys.version_info < (3, 10):
    print("Python 3.10+ is required for WeChat Director.", file=sys.stderr)
    raise SystemExit(2)

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from console_encoding import configure_console

configure_console()

from director_core import ASSETS_DIR, get_skill_root, get_workspace_root


def check_python():
    v = sys.version_info
    ok = (v.major, v.minor) >= (3, 10)
    return [f"{'✅' if ok else '⚠️'} Python {v.major}.{v.minor}（需要 3.10+）"], ok


def check_optional_deps():
    issues = []
    try:
        import PIL  # noqa: F401
        issues.append("✅ Pillow（封面拼接 / 尺寸校验必需）")
    except ImportError:
        issues.append("⚠️ Pillow 未安装（封面拼接与尺寸校验将跳过）—— pip install Pillow")
    try:
        import tinify  # noqa: F401
        issues.append("✅ tinify（可选：TinyPNG 压缩）")
    except ImportError:
        issues.append("ℹ️ tinify 未安装（可选：图片压缩）")
    try:
        from qcloud_cos import CosConfig  # noqa: F401
        issues.append("✅ cos-python-sdk-v5（可选：上传腾讯云 COS）")
    except ImportError:
        issues.append("ℹ️ cos-python-sdk-v5 未安装（可选：COS 上传）")
    return issues


def check_obsidian_cli():
    if shutil.which("obsidian"):
        return ["✅ Obsidian CLI 已安装（用于给草稿写 visual_ready 属性）"]
    return ["ℹ️ Obsidian CLI 未安装（该增强步骤自动跳过，不影响生图）"]


def check_scripts():
    skill_root = get_skill_root()
    required = [
        "scripts/visualize.py",
        "scripts/director_core.py",
        "scripts/brief_parser.py",
        "scripts/workspace.py",
        "scripts/console_encoding.py",
        "scripts/providers/gemini.py",
        "scripts/providers/gpt_image2.py",
    ]
    issues, ok = [], True
    for rel in required:
        if (skill_root / rel).exists():
            issues.append(f"  ✅ {rel}")
        else:
            issues.append(f"  ❌ {rel} 未找到")
            ok = False
    return issues, ok


def check_ip_assets():
    ref = ASSETS_DIR / "IP_Reference.png"
    if ref.exists():
        return [f"✅ IP 参考图就绪：{ref.name}"]
    return [f"ℹ️ 未找到 IP 参考图 {ref.name}；IP 模式将降级为纯文字描述"]


def check_providers(api_config):
    """只读列出已配置渠道；不生成、不收费。"""
    if not api_config:
        return ["ℹ️ 未读到 conductor/api_keys.json —— 可用当前 Agent / 平台生图能力，或新增第三方 API"]
    rows = []
    for name, conf in api_config.items():
        if not isinstance(conf, dict) or name in ("tinify", "cos"):
            continue
        rows.append(f"  · {name}: model={conf.get('model', '—')} adapter={conf.get('adapter', '—')} "
                    f"key={'有' if conf.get('api_key') else '无'}")
    return rows or ["ℹ️ api_keys.json 中没有可用的生图渠道段"]


def run_check(workspace=None, source_file=None):
    print("=" * 52)
    print("🎬  WeChat Director 配置检测")
    print("=" * 52)

    print("\n🔧 环境检查:")
    py_msgs, _ = check_python()
    for m in py_msgs:
        print("  " + m)
    for m in check_optional_deps():
        print("  " + m)
    for m in check_obsidian_cli():
        print("  " + m)

    print("\n📦 脚本检查:")
    script_msgs, scripts_ok = check_scripts()
    for m in script_msgs:
        print(m)

    print("\n🖼️  IP 资源:")
    for m in check_ip_assets():
        print("  " + m)

    workspace_root = get_workspace_root(source_file=source_file, explicit=workspace)
    print("\n📁 文章工作区:")
    if workspace_root is None:
        print("  ⚠️ 未定位到工作区（需要含 articles/ + published/，或 Obsidian vault 根）")
        print("     → 请用 --workspace 指定，或设置 WECHAT_WORKSPACE 环境变量")
        api_config = {}
    else:
        print(f"  ✅ {workspace_root}")
        config_path = workspace_root / "conductor" / "api_keys.json"
        if config_path.exists():
            try:
                api_config = json.loads(config_path.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"  ⚠️ api_keys.json 解析失败：{e}")
                api_config = {}
        else:
            print("  ℹ️ conductor/api_keys.json 不存在（第三方 API 渠道未配置）")
            api_config = {}

    print("\n🎨 已配置生图渠道（只读）:")
    for m in check_providers(api_config):
        print(m)

    print()
    if not scripts_ok:
        print("❌ 脚本不完整，请重新安装技能后继续。")
        return 1

    print("✅ Director 环境就绪。")
    print("   每次 /draw 都会重新检测渠道并要求显式选择，不使用默认值代选。")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", help="文章工作区根（显式指定）")
    parser.add_argument("--source-file", help="稿件路径，用于推断工作区")
    args = parser.parse_args()
    sys.exit(run_check(workspace=args.workspace, source_file=args.source_file))

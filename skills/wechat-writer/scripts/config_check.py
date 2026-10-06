#!/usr/bin/env python3
"""
config_check.py - WeChat Writer 配置检测
首次触发时自动运行，检查写作环境是否就绪。

返回状态:
  0 - 所有检查通过
  1 - 有配置缺失或问题（仍可继续，但功能受限）
"""

import json
import argparse
import sys
if sys.version_info < (3, 10):
    print("Python 3.10+ is required for WeChat Writer.", file=sys.stderr)
    raise SystemExit(2)
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from console_encoding import configure_console

configure_console()

# --- 路径解析 ---
# 确保同目录脚本可被 import（workspace 共享解析模块）
sys.path.insert(0, str(Path(__file__).resolve().parent))
from workspace import resolve_workspace

def get_workspace_root(source_file=None, explicit=None):
    # 显式 > 环境变量 > cwd 结构标记 > source_file 结构标记 > None
    # 不再从脚本自身位置硬推算（技能可能被安装到托管目录，推算结果必然错误）
    root, method = resolve_workspace(source_file=source_file, explicit=explicit)
    return root

def get_skill_root():
    return Path(__file__).resolve().parent.parent  # wechat-writer/

def get_knowledge_dir(source_file=None, explicit=None):
    root = get_workspace_root(source_file, explicit)
    return root / "knowledge" if root else None

# --- 检测逻辑 ---

def check_python():
    issues = []
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 10):
        issues.append(f"⚠️ Python {version.major}.{version.minor}（需要 3.10+）")
    else:
        issues.append(f"✅ Python {version.major}.{version.minor}")
    return issues

def check_obsidian_cli():
    issues = []
    if shutil.which("obsidian"):
        issues.append("✅ Obsidian CLI 已安装（用于文件属性写入）")
    else:
        issues.append("ℹ️ Obsidian CLI 未安装（archive 功能将降级为手动模式，不影响写作流程）")
    return issues

def check_scripts():
    issues = []
    skill_root = get_skill_root()
    required_scripts = [
        "scripts/article_assets.py",
        "scripts/workspace.py",
        "scripts/console_encoding.py",
        "scripts/cleaner.py",
        "scripts/research.py",
        "scripts/review_toolkit.py",
        "scripts/archive.py",
        "scripts/material_store.py",
        "scripts/memory_store.py",
    ]
    for script in required_scripts:
        if (skill_root / script).exists():
            issues.append(f"  ✅ {script}")
        else:
            issues.append(f"  ❌ {script} 未找到")
    return issues

def check_personal_files(source_file=None, explicit=None):
    """检测需要用户个人化的文件"""
    issues = []
    knowledge_dir = get_knowledge_dir(source_file, explicit)
    if knowledge_dir is None:
        return ["  ℹ️ 未定位文章工作区，请指定 --workspace 或 --source-file；技能 knowledge 仅为模板"]
    personal_files = {
        "style_guide_david.md": "当前工作区写作风格指南",
        "team_memory.md": "当前工作区团队记忆",
    }
    for filename, description in personal_files.items():
        file_path = knowledge_dir / filename
        if file_path.exists():
            issues.append(f"  ✅ knowledge/{filename} - {description}；技能同名文件仅模板")
        else:
            issues.append(f"  ℹ️ {filename} 不存在（可跳过）")
    return issues

def run_check(source_file=None, explicit=None):
    print("=" * 50)
    print("✍️  WeChat Writer 配置检测")
    print("=" * 50)
    print()

    # Python 版本
    print("🔧 环境检查:")
    for msg in check_python():
        print(f"  {msg}")
    for msg in check_obsidian_cli():
        print(f"  {msg}")
    print()

    # 脚本完整性
    print("📦 脚本检查:")
    script_checks = check_scripts()
    for msg in script_checks:
        print(msg)
    print()

    # 个人化文件提示
    print("👤 个人化文件（首次使用前建议检查）:")
    for msg in check_personal_files(source_file, explicit):
        print(msg)
    print()

    if any("❌" in msg for msg in script_checks):
        print("❌ WeChat Writer 脚本不完整，请重新安装技能后继续。")
        return 1
    print("✅ WeChat Writer 环境就绪。")
    print("   写作流程不依赖 API key，可直接开始使用 /interview 或 /write。")
    print()
    knowledge_dir = get_knowledge_dir(source_file, explicit)
    if knowledge_dir is None:
        print("   💡 请先选择文章工作区（--workspace 或 --source-file）；技能 knowledge 仅为模板。")
    elif any(not (knowledge_dir / name).exists() for name in ("style_guide_david.md", "team_memory.md")):
        print("   💡 可按需在当前工作区 knowledge/ 初始化风格指南和团队记忆；这两项不是写作必需条件。")
    return 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace")
    parser.add_argument("--source-file")
    args = parser.parse_args()
    sys.exit(run_check(args.source_file, args.workspace))

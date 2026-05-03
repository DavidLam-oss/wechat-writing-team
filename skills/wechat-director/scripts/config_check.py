#!/usr/bin/env python3
"""
config_check.py - WeChat Director 配置检测
首次触发时自动运行，检查生图相关配置是否就绪。

返回状态:
  ok              - 至少有一个可用的生图 provider
  optional_missing - 无 provider（用户可选择手动生图或跳过）
"""

import json
import sys
from pathlib import Path

# --- 路径解析（与 visualize.py 保持一致，支持任意目录名）---

def get_workspace_root():
    """Find the workspace root: parent of the repo (contains David-Writing-Team and conductor/ as siblings)."""
    script_dir = Path(__file__).resolve().parent
    # go up: scripts -> wechat-director -> Skills -> David-Writing-Team -> parent
    repo_root = script_dir.parent.parent.parent  # David-Writing-Team/
    return repo_root.parent  # parent that contains both David-Writing-Team and conductor

def get_skill_root():
    """Find the wechat-director skill root (parent of scripts/)."""
    return Path(__file__).resolve().parent.parent  # scripts -> wechat-director

def load_api_config():
    config_path = get_workspace_root() / "conductor" / "api_keys.json"
    if not config_path.exists():
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

# --- 配置检测逻辑 ---

def check_image_providers(api_config):
    """检测生图 provider"""
    issues = []
    providers = []

    # 1. Gemini API（需要 api_key）
    gemini = api_config.get("gemini", {})
    if gemini.get("api_key") and gemini.get("base_url"):
        providers.append("gemini")
    elif gemini.get("api_key"):
        issues.append("⚠️ gemini.api_key 已配置，但缺少 base_url")
    else:
        issues.append("ℹ️ gemini 未配置（可选，需要 API key）")

    # 2. GPT-Image2（需要 api_key）
    gpt = api_config.get("gpt-image2", {})
    if gpt.get("api_key") and gpt.get("base_url"):
        providers.append("gpt-image2")
    elif gpt.get("api_key"):
        issues.append("⚠️ gpt-image2.api_key 已配置，但缺少 base_url")
    else:
        issues.append("ℹ️ gpt-image2 未配置（可选，需要 API key）")

    return providers, issues

def check_optional_services(api_config):
    """检测可选服务"""
    issues = []

    # TinyPNG 压缩
    tinify = api_config.get("tinify", {})
    if tinify.get("api_key"):
        issues.append("✅ TinyPNG 压缩已配置")
    else:
        issues.append("ℹ️ TinyPNG 压缩未配置（可选，图片将不压缩）")

    # 腾讯云 COS 上传
    cos = api_config.get("cos", {})
    required = ["region", "secret_id", "secret_key", "bucket"]
    if all(cos.get(k) for k in required):
        issues.append("✅ 腾讯云 COS 上传已配置")
    else:
        issues.append("ℹ️ 腾讯云 COS 未配置（可选，图片将不上传到 CDN）")

    return issues

def run_check():
    api_config = load_api_config()
    providers, provider_issues = check_image_providers(api_config)
    optional_issues = check_optional_services(api_config)

    has_provider = len(providers) > 0

    print("=" * 50)
    print("🎬 WeChat Director 配置检测")
    print("=" * 50)
    print()

    print("📦 生图 Provider 状态:")
    for issue in provider_issues:
        print(f"  {issue}")
    print()

    if has_provider:
        print(f"✅ 可用 provider: {', '.join(providers)}")
        print()
        print("▶️  可选服务状态:")
        for issue in optional_issues:
            print(f"  {issue}")
        print()
        print("✅ 配置检测通过，Director 可以自动生图。")
        print("   如需跳过，可在 /draw 时选择手动生图或使用已有图片链接。")
        return 0
    else:
        print("⚠️  没有配置任何生图 provider")
        print()
        print("   📋 选择方案:")
        print("   1. 配置 API key（推荐 Gemini 或 GPT-Image2）：")
        print("      → 在 conductor/api_keys.json 中添加 gemini 或 gpt-image2 配置")
        print("   2. 跳过: 手动生图，在 Storyboard 中填入图片 URL")
        print()
        print(f"   配置路径: {get_workspace_root()}/conductor/api_keys.json")
        return 1

if __name__ == "__main__":
    sys.exit(run_check())
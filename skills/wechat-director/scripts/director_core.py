#!/usr/bin/env python3
"""WeChat Director —— 基础设施层。

日志、常量表、路径解析、配置加载、文本工具。
从 visualize.py 拆出（2026-10-05）；不依赖任何兄弟模块。
"""
import hashlib
import json
import logging
import re
import sys
from pathlib import Path

# 让本模块被任意方式加载时，都能 import 同目录的 workspace 模块
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from workspace import resolve_workspace

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

ASPECT_RATIOS = {
    "cover-main": {"width": 1504, "height": 640, "suffix": "cover-main"},
    "cover-sidebar": {"width": 1024, "height": 1024, "suffix": "cover-sidebar"},
    "illustration": {"width": 768, "height": 1024, "suffix": "illustration"},
    "quote": {"width": 768, "height": 1024, "suffix": "quote"},
}


DIRECTOR_VERSION = "2.5.0"

# IP 参考图所在目录。刻意只在这里推算一次：本模块位于 scripts/ 下，
# 深度天然正确；providers/ 子包内的模块若各自推算 __file__，必然少算一层。
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


def get_skill_root():
    """技能根目录（wechat-director/）。

    技能被复制到任何位置、任何宿主（Claude Code / Codex / Gemini CLI）都按
    自身目录解析资源，不使用机器绝对路径。
    """
    return Path(__file__).resolve().parent.parent


def get_workspace_root(source_file=None, explicit=None):
    """定位**文章工作区根**（含 `articles/` + `published/`，或 Obsidian vault 根 `.obsidian/`）。

    解析顺序：显式 `--workspace` > `WECHAT_WORKSPACE` 环境变量 >
    当前目录结构标记 > source_file 向上结构标记 > None。
    不再从脚本自身位置硬推算 —— 技能被安装到托管目录（`~/.claude/skills`、
    `~/.codex/skills` 等）时，推算结果必然错误。
    """
    root, _ = resolve_workspace(source_file=source_file, explicit=explicit)
    return root


def load_api_config(source_file=None, explicit=None):
    """Load API keys from <workspace>/conductor/api_keys.json"""
    workspace_root = get_workspace_root(source_file=source_file, explicit=explicit)
    if workspace_root is None:
        logger.warning(
            "⚠️ 未定位到文章工作区（缺少 articles/ + published/ 结构标记）。"
            "请用 --workspace 指定工作区根，或设置 WECHAT_WORKSPACE 环境变量。")
        return {}

    config_path = workspace_root / "conductor" / "api_keys.json"
    if not config_path.exists():
        logger.warning("⚠️ API Config not found. API providers, compression, and upload may be unavailable.")
        return {}

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    return config


# --- Helper Functions ---

def sanitize_filename(text):
    text = re.sub(r'[<>:"/\\|?*]', '', text)
    text = re.sub(r'\s+', '-', text)
    return text[:50]


def clean_prompt(prompt):
    prompt = prompt.strip()
    if len(prompt) < 5: return None
    prompt = re.sub(r',?\s*aspect ratio\s*[\d.:]+', '', prompt, flags=re.IGNORECASE)
    prompt = re.sub(r'\s--\w+(?:\s+[\w.:]+)?', '', prompt)
    return prompt.strip()


def check_ip_requirement(text):
    return bool(re.search(r'(?:IP(?:形象)?|Reference|参考图?)\s*[:：]\s*(?:Yes|True|是|On|Required|1)', text, re.IGNORECASE))


def calculate_hash(prompt, width, height, model, use_ip=False):
    content = f"{prompt}|{width}|{height}|{model}|{use_ip}"
    return hashlib.md5(content.encode('utf-8')).hexdigest()[:8]


def require_config(api_config, provider_name, required_keys):
    if not api_config:
        raise RuntimeError(f"{provider_name} config missing.")

    missing = [key for key in required_keys if not api_config.get(key)]
    if missing:
        missing_str = ", ".join(missing)
        raise RuntimeError(f"{provider_name} config incomplete: missing {missing_str}.")

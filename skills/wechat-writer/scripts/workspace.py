#!/usr/bin/env python3
"""
workspace.py - 工作区与知识库路径自动检测（Agent 通用化）

背景：wechat-writer / wechat-director 两技能脚本原先从"脚本自身位置"硬推算工作区根，
当技能被安装到托管目录（如 ~/.skills-manager/skills、~/.trae-cn/skills）时，
推算结果指向用户主目录等错误路径，导致 conductor/api_keys.json、
articles/、published/ 全部定位失败。

本模块将工作区根解析统一为「显式 > 环境变量 > cwd 结构标记 > source_file 结构标记 > 兜底 None」。

约定：
  - 两技能各自 scripts/ 下各保留一份本文件，wechat-writer 为主源，修改必须同步到
    wechat-director（保持文件内容一致）。
  - 结构标记 = 目录含 articles/ + published/（wechat-writer 特征），或含 .obsidian/（Obsidian vault 根）。
  - 兜底返回 None + method="none"，绝不回退脚本位置推算。

检测顺序（resolve_workspace）：
  1. explicit（--workspace / JSON workspace_root），校验目录存在
  2. 环境变量 WECHAT_WORKSPACE
  3. cwd 自身含结构标记（Agent 当前工作目录为根）
  4. source_file 向上遍历找结构标记（取最近祖先）
  5. 全部失败 -> (None, "none")
"""

from __future__ import annotations

import os
from pathlib import Path

# 工作区结构标记：wechat-writer 特征目录
WORKSPACE_MARKERS = ("articles", "published")
# Obsidian vault 根标记
VAULT_MARKER = ".obsidian"
# 环境变量名
ENV_WORKSPACE = "WECHAT_WORKSPACE"


def _find_workspace_from(start: Path) -> Path | None:
    """从 start 向上遍历，返回最近的工作区根；无则 None。"""
    current = Path(start).resolve()
    while True:
        if has_workspace_structure(current):
            return current
        if current.parent == current:
            break
        current = current.parent
    return None


def has_workspace_structure(path: Path) -> bool:
    """目录是否为工作区根：含 articles/+published/，或含 .obsidian/。"""
    p = Path(path)
    if not p.is_dir():
        return False
    if (p / VAULT_MARKER).exists():
        return True
    return all((p / m).is_dir() for m in WORKSPACE_MARKERS)


def detect_from_cwd(cwd=None) -> Path | None:
    """cwd 自身（或向上）是否处于工作区内；是则返回最近工作区根。"""
    base = Path(cwd).resolve() if cwd else Path.cwd().resolve()
    return _find_workspace_from(base)


def detect_from_source(source_file) -> Path | None:
    """从 source_file 所在目录向上找最近的工作区根；无则 None。"""
    if not source_file:
        return None
    src = Path(source_file).resolve()
    start = src if src.is_dir() else src.parent
    return _find_workspace_from(start)


def resolve_workspace(cwd=None, source_file=None, explicit=None):
    """按优先级解析工作区根。

    Returns:
        (Path | None, method)
        method ∈ {"explicit", "env", "cwd", "source", "none"}
    """
    # 1. 显式参数（最高优先）
    if explicit:
        p = Path(explicit)
        if not p.is_absolute() and cwd:
            p = Path(cwd) / p
        if p.exists() and p.is_dir():
            return p.resolve(), "explicit"
        # 显式指定但目录不存在：明确返回 None，交由调用方报错
        return None, "explicit"

    # 2. 环境变量
    env_ws = os.environ.get(ENV_WORKSPACE)
    if env_ws:
        p = Path(env_ws)
        if p.exists() and p.is_dir():
            return p.resolve(), "env"

    # 3. cwd 结构标记
    cw = detect_from_cwd(cwd)
    if cw:
        return cw, "cwd"

    # 4. source_file 向上找结构标记
    sw = detect_from_source(source_file)
    if sw:
        return sw, "source"

    # 5. 兜底：None（绝不回退脚本位置推算）
    return None, "none"


def get_workspace_root(cwd=None, source_file=None, explicit=None) -> Path | None:
    """便捷封装：仅返回根路径，无则 None。"""
    root, _ = resolve_workspace(cwd=cwd, source_file=source_file, explicit=explicit)
    return root


if __name__ == "__main__":
    root, method = resolve_workspace()
    if root:
        print(f"[Workspace] {root} (via {method})")
    else:
        print("[Workspace] none")

#!/usr/bin/env python3
"""WeChat Director —— Obsidian CLI 桥接层。"""
import json
import shutil
import subprocess
from pathlib import Path

from director_core import get_workspace_root, logger

def run_obsidian_cmd(args):
    """Run an obsidian CLI command and return success status and output."""
    try:
        if shutil.which("obsidian") is None:
            return False, "obsidian CLI not found in PATH"
            
        # Execute the actual command
        # Obsidian 1.12.7 CLI uses positional KV pairs like name=val path=path
        result = subprocess.run(["obsidian"] + args, capture_output=True, text=True, check=True)
        
        # CRITICAL: Obsidian CLI often exits with 0 even on error.
        output = (result.stdout + result.stderr).strip()
        if "Error:" in output or "not found" in output or "Missing required parameter" in output:
            return False, output
            
        return True, output
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False, ""


def get_obsidian_vault_root(start_path=None):
    """从给定路径向上寻找 `.obsidian` 配置目录，返回真正的 vault 根。

    找不到时回退到**文章工作区根**（可能为 None）——
    不再假定「仓库根 = vault 根」，那样会让任意路径都被误判为「在 vault 内」。
    """
    if start_path is None:
        start_path = Path(__file__).resolve()

    current = Path(start_path).resolve()
    if current.is_file():
        current = current.parent
    while current.parent != current:
        if (current / ".obsidian").is_dir():
            return current
        current = current.parent

    return get_workspace_root()


def get_obsidian_path(abs_path):
    """Convert absolute path to vault-relative path for Obsidian CLI."""
    # Obsidian CLI expects paths RELATIVE to the REAL vault root.
    vault_root = get_obsidian_vault_root()
    try:
        # Ensure we are working with absolute resolved paths
        target_path = Path(abs_path).resolve()
        rel_path = target_path.relative_to(vault_root)
        return str(rel_path)
    except Exception:
        # If path is not under vault_root, return as is (Obsidian will likely fail anyway)
        return str(abs_path)


def is_obsidian_reachable(file_path):
    """Check if a file path is located within the current Obsidian vault."""
    vault_root = get_obsidian_vault_root(start_path=file_path)
    if vault_root is None:
        return False
    try:
        Path(file_path).resolve().relative_to(vault_root)
        return True
    except (ValueError, RuntimeError):
        return False


def set_obsidian_properties(file_path, properties):
    """Set multiple properties using Obsidian CLI."""
    if not is_obsidian_reachable(file_path):
        return False
        
    rel_path = get_obsidian_path(file_path)
    success_count = 0
    total_props = len([v for v in properties.values() if v is not None])
    
    for key, value in properties.items():
        if value is None: continue
        # Format: property:set name=key value=val path=path
        val_str = json.dumps(value) if isinstance(value, list) else str(value)
        
        # Use Obsidian 1.12 syntax: property:set name=... value=... path=...
        cmd_args = ["property:set", f"name={key}", f"value={val_str}", f"path={rel_path}"]
        ok, err = run_obsidian_cmd(cmd_args)
        if ok:
            success_count += 1
        else:
            logger.warning(f"⚠️ CLI Property set failed for {key}: {err}")
            
    return success_count == total_props


def obsidian_open(file_path):
    """Open a file in Obsidian GUI."""
    if not is_obsidian_reachable(file_path):
        return False
        
    rel_path = get_obsidian_path(file_path)
    # Use Obsidian 1.12 syntax: open path=...
    ok, err = run_obsidian_cmd(["open", f"path={rel_path}"])
    if not ok:
        logger.warning(f"⚠️ CLI Open failed: {err}")
    return ok

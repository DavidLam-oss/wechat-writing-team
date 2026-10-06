#!/usr/bin/env python3
import json
import argparse
import shutil
import re
import subprocess
import sys
from pathlib import Path
from datetime import datetime

# 确保同目录脚本可被 import（workspace 共享解析模块）
sys.path.insert(0, str(Path(__file__).resolve().parent))
from console_encoding import configure_console
from workspace import resolve_workspace
from article_assets import plan_asset, prepare_markdown, verify_published

configure_console()

# 36 Official Whitelist Tags for blog and WeChat articles
WHITELIST_TAGS = {
    # 知识管理类
    "Obsidian", "Obsidian入门", "知识管理", "Obsidian插件", "笔记同步", "Web剪藏",
    # AI与智能体
    "AI Agent", "AI模型", "Claude Code", "Codex", "WorkBuddy", "OpenClaw", "提示词工程", "MCP",
    # 效率与工具
    "效率工具", "自动化", "苹果生态", "终端命令行", "Raycast", "Typeless", "任务管理",
    # 编程与开源
    "编程开发", "AI编程", "开源",
    # 创作与发布
    "内容创作", "微信公众号", "WeChat Converter", "多平台分发", "排版与导出",
    # 运维与建站
    "服务器运维", "SEO与数据分析",
    # 个人与思考
    "生活随笔", "个人成长", "职场思考", "复盘与踩坑", "副业与出海",
}

WHITELIST_OBSIDIAN_SECTIONS = {
    "first-steps",
    "basics",
    "plugins-automation",
    "advanced-organization",
    "ai-workflow",
    "collecting",
    "sync-backup",
    "publishing",
}


def validate_frontmatter_rules(fm, title=""):
    """校验博客/公众号 Frontmatter 规则，返回警告列表。

    1. excerpt：50-100 字（>120 为硬上限）。
    2. tags：2-4 个，且必须严格取自 36 个官方白名单。
    3. Obsidian 相关文章：tags 必须含 'Obsidian'；obsidianSection 必须为 8 个合法值之一。
    """
    warnings = []

    excerpt = "" if fm.get('excerpt') is None else str(fm.get('excerpt')).strip()
    excerpt_len = len(excerpt)
    if excerpt_len > 120:
        warnings.append(f"⚠️ Excerpt length is {excerpt_len} (>120). Please shorten it in Stage 3.")
    elif excerpt_len < 50 or excerpt_len > 100:
        warnings.append(f"⚠️ Excerpt length is {excerpt_len} (expected 50-100 chars for blog frontmatter).")

    raw_tags = fm.get('tags')
    if not isinstance(raw_tags, list):
        warnings.append("⚠️ Frontmatter 'tags' must be a list containing 2-4 tags from the whitelist.")
        tags_list = []
    else:
        tags_list = [str(t).strip() for t in raw_tags if str(t).strip()]
        if not (2 <= len(tags_list) <= 4):
            warnings.append(f"⚠️ Tags count is {len(tags_list)} (expected 2-4 tags).")
        invalid_tags = [t for t in tags_list if t not in WHITELIST_TAGS]
        if invalid_tags:
            warnings.append(f"⚠️ Invalid tag(s) found: {invalid_tags}. Must be strictly chosen from the 36 official whitelist tags.")

    raw_section = fm.get('obsidianSection', '')
    obsidian_section = raw_section.strip() if isinstance(raw_section, str) else ''

    is_obsidian_related = (
        'obsidian' in str(title).lower() or
        bool(obsidian_section) or
        any('obsidian' in t.lower() for t in tags_list)
    )

    if is_obsidian_related and "Obsidian" not in tags_list:
        warnings.append("⚠️ Obsidian-related article must include 'Obsidian' in tags.")

    if obsidian_section and obsidian_section not in WHITELIST_OBSIDIAN_SECTIONS:
        allowed_list = sorted(list(WHITELIST_OBSIDIAN_SECTIONS))
        warnings.append(f"⚠️ Invalid obsidianSection: '{obsidian_section}'. Allowed values: {allowed_list}")

    return warnings


def run_obsidian_cmd(args):
    """Run an obsidian CLI command and return success status and output."""
    try:
        if shutil.which("obsidian") is None:
            return False, "obsidian CLI not found in PATH"
            
        # Execute the actual command
        # Obsidian 1.12.7 CLI uses positional KV pairs like name=val path=path
        result = subprocess.run(["obsidian"] + args, capture_output=True, text=True, check=True)
        
        # CRITICAL: Obsidian CLI often exits with 0 even on error. 
        # We must scan stdout/stderr for error keywords.
        output = (result.stdout + result.stderr).strip()
        if "Error:" in output or "not found" in output or "Missing required parameter" in output:
            return False, output
            
        return True, output
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False, ""

def get_obsidian_vault_root(start_path=None):
    """Get the real Obsidian vault root by looking for the .obsidian configuration folder.

    Walks upward from the given path (default: this script's location) to find a
    vault. Returns None if no vault is found (instead of wrongly falling back to
    the workspace root, which would make arbitrary paths appear "in vault")."""
    if start_path is None:
        start_path = Path(__file__).resolve()
    
    current = Path(start_path)
    while current.parent != current:
        if (current / ".obsidian").is_dir():
            return current
        current = current.parent
    
    return None

def get_obsidian_path(abs_path):
    """Convert absolute path to vault-relative path for Obsidian CLI."""
    # Obsidian CLI expects paths RELATIVE to the REAL vault root.
    # The vault is located by walking upward from the target file itself.
    target_path = Path(abs_path).resolve()
    vault_root = get_obsidian_vault_root(start_path=target_path)
    if vault_root is None:
        return str(abs_path)
    try:
        rel_path = target_path.relative_to(vault_root)
        return str(rel_path)
    except ValueError:
        # If path is not under vault_root, return as is (Obsidian will likely fail anyway)
        return str(abs_path)

def is_obsidian_reachable(file_path):
    """Check if a file path is located within the current Obsidian vault."""
    target_path = Path(file_path).resolve()
    vault_root = get_obsidian_vault_root(start_path=target_path)
    if vault_root is None:
        return False
    try:
        target_path.relative_to(vault_root)
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
        val_str = json.dumps(value, ensure_ascii=False) if isinstance(value, list) else str(value)
        
        # Use Obsidian 1.12 syntax: property:set name=... value=... path=...
        cmd_args = ["property:set", f"name={key}", f"value={val_str}", f"path={rel_path}"]
        ok, err = run_obsidian_cmd(cmd_args)
        if ok: 
            success_count += 1
        else:
            print(f"⚠️ CLI Property set failed for {key}: {err}")
            
    return success_count == total_props # Only return True if ALL succeeded

def get_workspace_root(source_file=None, explicit=None):
    """工作区根：显式 > 环境变量 > cwd 结构标记 > source_file 结构标记 > None。

    不再从脚本自身位置硬推算（技能可能被安装到托管目录，推算结果必然错误）。
    """
    root, method = resolve_workspace(source_file=source_file, explicit=explicit)
    if root:
        print(f"[Workspace] {root} (via {method})")
    return root

def sanitize_filename(name):
    return re.sub(r'[<>:"/\\|?*]', '', name).strip()

def yaml_escape(value):
    """Escape text for YAML double-quoted string values."""
    text = "" if value is None else str(value)
    return text.replace("\\", "\\\\").replace('"', '\\"')

def pick_cover_image(img_dir):
    """Pick cover image from archived image folder.

    Priority:
    1. Exact match: *cover-combined.jpg (old naming)
    2. Exact match: *cover-main.jpg (old naming)
    3. Partial match: *_cover-combined*
    4. Partial match: *_cover-main*
    （子串匹配对新命名 {prefix}_cover-*.jpg 与旧命名 cover-*.jpg 均兼容）
    """
    if not img_dir.exists() or not img_dir.is_dir():
        return None

    # 1. Try exact matches (simple naming preference)
    exact_priorities = ["cover-combined.jpg", "cover-main.jpg"]
    for name in exact_priorities:
        f = img_dir / name
        if f.exists():
            return f

    # 2. Fallback to sorting and partial match
    image_exts = {".jpg", ".jpeg", ".png", ".webp"}
    image_files = sorted(
        [
            p for p in img_dir.iterdir()
            if p.is_file() and p.suffix.lower() in image_exts
        ],
        key=lambda p: p.name.lower()
    )

    if not image_files:
        return None

    priorities = ("_cover-combined", "cover-combined", "_cover-main", "cover-main")
    for keyword in priorities:
        for file_path in image_files:
            if keyword in file_path.name.lower():
                return file_path

    return None

def update_index(title, excerpt, filename, workspace_root=None):
    """
    更新 published_article_index.md（运行数据，位于工作区 conductor/）
    - title: 文章标题（用于 Obsidian Wiki Link 和显示）
    - excerpt: 摘要
    - filename: 实际保存的文件名（不含扩展名），暂不使用
    - workspace_root: 工作区根；缺失时拒绝更新，避免写入技能目录
    """
    if not workspace_root:
        raise RuntimeError("workspace_root is required; published index belongs to workspace/conductor")
    index_path = workspace_root / "conductor" / "published_article_index.md"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    if not index_path.exists():
        print(f"Creating index file: {index_path}")
        index_path.write_text(
            "# 已发布文章索引 (Published Article Index)\n\n"
            "> 运行数据：由 archive.py 自动维护。\n\n",
            encoding='utf-8'
        )

    # Obsidian Wiki Link: 使用纯标题格式 [[标题]]
    link = f"[[{title}]]"

    # 归档索引是 Markdown 表格，摘要中的竖线和换行必须转义，否则会破坏表格结构。
    safe_excerpt = " ".join(str(excerpt or "").replace("|", "\\|").splitlines()).strip()
    line = f"| {link} | {safe_excerpt} |"
    month_header = f"## {datetime.now().strftime('%Y-%m')}"

    try:
        content = index_path.read_text(encoding='utf-8')
        # Avoid duplicates (can happen if index update logic changes or a rerun occurs).
        if link in content:
            print(f"Index already contains entry: {link}")
            return True

        lines = content.splitlines()

        if month_header not in content:
            # Create new month section at the TOP (before first existing month)
            # Find the first '## YYYY-MM' line (month header)
            insert_pos = len(lines)  # First month follows the introductory heading/notes.
            for i, l in enumerate(lines):
                if l.strip().startswith('## 20'):  # Match '## 2025-xx' or '## 2026-xx'
                    insert_pos = i
                    break

            new_section = [
                "",
                month_header,
                "",
                "| 标题 | 摘要 |",
                "| --- | --- |",
                line,
            ]
            lines[insert_pos:insert_pos] = new_section
            index_path.write_text('\n'.join(lines), encoding='utf-8')
            print(f"Created new month section at top: {index_path}")
            return True
        else:
            # Insert after the table header for the month section.
            for i, l in enumerate(lines):
                if l.strip() == month_header:
                    # Find the separator row of the markdown table, which can be either
                    # `| --- | --- |` or a custom dash-width row.
                    for j in range(i + 1, min(i + 30, len(lines) - 1)):
                        cur = lines[j].strip()
                        nxt = lines[j + 1].strip()
                        if not cur.startswith("|") or not nxt.startswith("|"):
                            continue
                        # The second line should look like a separator row with dashes.
                        if "-" not in nxt:
                            continue
                        lines.insert(j + 2, line)
                        index_path.write_text('\n'.join(lines), encoding='utf-8')
                        print(f"Updated index: {index_path}")
                        return True

            # If header found but table structure not found (rare), append in-place under the header.
            with index_path.open('a', encoding='utf-8') as f:
                 f.write(f"\n{line}\n")
            return True

    except Exception as e:
        print(f"Error updating index: {e}")
        return False

def strip_frontmatter(content):
    if content.startswith("---\n"):
        parts = content.split("\n---\n", 1)
        if len(parts) >= 2: return parts[1].lstrip()
    return content

def strip_h1_title(content):
    """去除开头的一级标题（如 # 02_Draft: xxx）"""
    lines = content.split('\n')
    if lines and lines[0].startswith('# '):
        return '\n'.join(lines[1:]).lstrip()
    return content

def strip_draft_metadata(content):
    """去除 Draft 文件开头的元信息块（仅当包含特定元数据关键词时才删除）

    元数据块特征:
    > **版本**: v2
    > **主笔**: 冰清
    > ...

    ---
    """
    lines = content.split('\n')
    if not lines:
        return content

    # 1. 预读开头的引用块
    i = 0
    quote_lines = []
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('>'):
            quote_lines.append(line)
            i += 1
        elif line == '':
            i += 1 # 允许引用块中间有空行（虽然标准Markdown引用块通常连续，但容错）
        else:
            break # 遇到非引用非空行，停止

    # 2. 检查是否包含元数据关键词
    # 必须包含至少一个强特征词，才认为是Draft Metadata
    quote_text = "".join(quote_lines)
    metadata_keywords = ["**版本**", "**主笔**", "**创建时间**", "**Version**", "**Author**"]
    is_metadata = any(keyword in quote_text for keyword in metadata_keywords)

    if not is_metadata:
        return content # 认为是正文引用，不作处理

    # 3. 如果确认是元数据，执行删除逻辑
    # i 此时停留在引用块之后的第一行（非空行，或者文件末尾）

    # 检查是否紧跟分隔线
    # 回溯一下，因为上面的循环可能跳过了引用块后的空行
    # 我们重新定位删除的截止点

    delete_end_index = 0

    # 重新扫描一遍确定精确的删除边界
    j = 0
    has_seen_quote = False
    while j < len(lines):
        line = lines[j].strip()
        if line.startswith('>'):
            has_seen_quote = True
            j += 1
        elif line == '':
            j += 1
        elif line == '---':
            # 只有在已经看到过引用块的情况下，遇到分隔线才认为是元数据区的结束
            if has_seen_quote:
                j += 1 # 吞掉分隔线
                # 再吞掉分隔线后的空行
                while j < len(lines) and lines[j].strip() == '':
                    j += 1
                delete_end_index = j
                break
            else:
                # 没看到引用块就遇到了分隔线？不应该发生，保留原样
                return content
        else:
            # 遇到正文了，还没遇到分隔线？
            # 这种情况下，也许没有分隔线，只是引用块结束。
            # 为了安全，只在有分隔线的情况下才删除？
            # 没有明确分隔线时不删除，避免把正文首段误判为元信息。
            return content

    return '\n'.join(lines[delete_end_index:])

def process_archive(data, explicit_workspace=None):
    if not data.get('source_file'):
        print("❌ source_file is required")
        return 2
    source_file = Path(data.get('source_file', ''))
    fm = data.get('frontmatter', {})

    # --- Workspace Resolution ---
    # 显式参数 > 环境变量 > cwd 结构标记 > source_file 结构标记
    workspace_root = get_workspace_root(
        source_file=str(source_file) if source_file else None,
        explicit=explicit_workspace or data.get('workspace_root'),
    )
    if workspace_root is None:
        print("❌ 无法定位工作区根。请通过 --workspace 显式指定，或在 JSON 中提供 workspace_root 字段。")
        return 2

    # --- Security Validation (Move to top) ---
    # Ensure source file is inside 'articles/Project_*' before reading/writing anything.

    if source_file.exists():
        project_dir = source_file.parent
        allowed_parent = (workspace_root / "articles").resolve()
        try:
            current_parent = project_dir.parent.resolve()
        except Exception:
             current_parent = None

        if current_parent != allowed_parent:
             print(f"⚠️ Security Violation: Source file is in '{current_parent}', but must be in '{allowed_parent}' to be archived.")
             print("   Operation aborted to prevent unauthorized access or data loss.")
             return 2
    else:
        print("❌ Source draft does not exist; publication aborted")
        return 2

    title = fm.get('title', 'Untitled')
    safe_title = sanitize_filename(title)
    
    target_dir = workspace_root / "published"
    target_dir.mkdir(parents=True, exist_ok=True)
    
    target_file = target_dir / f"{safe_title}.md"
    
    # Read & Clean
    content = source_file.read_text(encoding='utf-8')
    content = strip_frontmatter(content)
    content = strip_h1_title(content)
    content = strip_draft_metadata(content)

    # Resolve Markdown references against the source project, then copy the files.
    try:
        content, asset_plans = prepare_markdown(content, source_file.parent)
        selected_cover = (fm.get('cover') or '').strip()
        if not selected_cover:
            selected = pick_cover_image(source_file.parent / "zpicture.assets")
            selected_cover = f"zpicture.assets/{selected.name}" if selected else ""
        if selected_cover:
            cover_plan = plan_asset(selected_cover, source_file.parent, allow_legacy_cover=True)
            if cover_plan:
                cover_source, selected_cover = cover_plan
                asset_plans[selected_cover] = cover_source
    except (OSError, ValueError) as exc:
        print(f"❌ Article assets incomplete; publication aborted: {exc}")
        return 1

    # Copy zpicture.assets/ folder to published/ and resolve cover path.
    # Keep explicit cover if provided by upstream input.
    # 项目目录（articles/Project_[Title]/）保留原位，不再移动归档。
    # cover 字段使用相对 published 文件的路径（如 zpicture.assets/cover-combined.jpg），
    # 不附加 vault 目录名前缀，保证 Obsidian 能正确解析。
    cover_path = selected_cover
    excerpt = "" if fm.get('excerpt') is None else str(fm.get('excerpt')).strip()
    for warning in validate_frontmatter_rules(fm, title):
        print(warning)
    if source_file.exists():
        project_dir = source_file.parent
        img_dir = project_dir / "zpicture.assets"

        if img_dir.exists() and img_dir.is_dir():
            # Keep fixed output directory name for plugin config compatibility.
            img_dest = target_dir / "zpicture.assets"
            try:
                # 合并复制：所有文章的图片共存于同一 published/zpicture.assets。
                # 图片来源为当前项目目录（articles/Project_[Title]/zpicture.assets），
                # 图片命名带文章标题前缀，跨文章不重名；同名文件更新（重发覆盖），异名文件保留。
                # 不再使用 zpicture_prev_* 备份挤压（旧逻辑会导致旧文章图片断链与目录堆积）。
                shutil.copytree(str(img_dir), str(img_dest), dirs_exist_ok=True)
                print(f"🖼️  Merged images into: {img_dest}")

            except Exception as e:
                print(f"❌ Image archive failed; publication aborted: {e}")
                return 1
    
    try:
        for destination, original in asset_plans.items():
            target = target_dir / destination
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists() or not original.is_relative_to(source_file.parent / "zpicture.assets"):
                shutil.copy2(original, target)
        verify_published(content, target_dir, cover_path)
    except (OSError, ValueError) as exc:
        print(f"❌ Published image links incomplete; publication aborted: {exc}")
        return 1

    # Generate properties dict
    props = {
        "title": title,
        "date": fm.get('date', datetime.now().strftime('%Y-%m-%d')),
        "slug": fm.get('slug', ''),
        "excerpt": excerpt,
        "cover": cover_path,
        "tags": fm.get('tags', []),
        "status": "published"
    }
    # 可选：透传 obsidianSection（Obsidian 专题页归类）。
    # 仅当来源 frontmatter 提供了合法值时写入，避免非 Obsidian 文章被空字段污染。
    obsidian_section = fm.get('obsidianSection', '')
    obsidian_section = obsidian_section.strip() if isinstance(obsidian_section, str) else ''
    if obsidian_section:
        props["obsidianSection"] = obsidian_section

    # Write & Update Properties
    # If Obsidian CLI is available, we attempt CLI-Native update
    cli_ok = shutil.which("obsidian") is not None
    cli_success = False
    
    if cli_ok and is_obsidian_reachable(target_file):
        # 1. Write content with empty FM shell
        target_file.write_text(f"---\n---\n{content}", encoding='utf-8')
        # 2. Set properties via CLI (Checking if ALL properties were set correctly)
        if set_obsidian_properties(target_file, props):
            print(f"🚀 Published article to: {target_file} (CLI-Native)")
            cli_success = True
        else:
            print(f"⚠️ CLI Property sync failed. Falling back to Legacy metadata writing...")
            cli_success = False

    if not cli_success:
        # Legacy / Fallback: Manual YAML-like construction
        # This is the 'Source of Truth' for metadata safety.
        obsidian_section_line = (
            f'obsidianSection: "{yaml_escape(props["obsidianSection"])}"\n'
            if props.get("obsidianSection") else ""
        )
        new_content = f"""---
title: "{yaml_escape(title)}"
date: "{props['date']}"
slug: "{yaml_escape(props['slug'])}"
excerpt: "{yaml_escape(props['excerpt'])}"
cover: "{yaml_escape(props['cover'])}"
tags: {json.dumps(props['tags'], ensure_ascii=False)}
{obsidian_section_line}status: published
---
{content}"""
        target_file.write_text(new_content, encoding='utf-8')
        if cli_ok:
            print(f"🚀 Published article to: {target_file} (Fallback-Mode)")
        else:
            print(f"🚀 Published article to: {target_file} (Legacy-Mode)")
    
    # Update Index
    # Pass filename (without extension) for Obsidian Wiki Link
    try:
        index_ok = update_index(title, excerpt, safe_title, workspace_root=workspace_root)
    except (OSError, ValueError) as exc:
        print(f"❌ Index update error: {exc}")
        index_ok = False
    if not index_ok:
        print("❌ Article and images saved, but index update failed. Retry the index update; publication is incomplete.")
        return 1

    # Project Folder 保留原位
    # 项目目录（articles/Project_[Title]/）不再移动归档，继续保留过程文件、草稿与图片；
    # conductor/archive/ 不再由本脚本创建或写入，发布副本仅位于 published/。
    if source_file.exists():
        print(f"📁 Project retained at: {source_file.parent} (articles 保留，不再归档到 conductor/archive)")

    # Memory Suggestion: display a confirmation card; never write silently.
    suggestion = f"- [{datetime.now().strftime('%Y-%m-%d')}] [Experience] Completed {title}."
    pending_path = workspace_root / "conductor" / "pending_memory_suggestions.json"
    pending_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        pending = json.loads(pending_path.read_text(encoding="utf-8")) if pending_path.exists() else []
        if not isinstance(pending, list):
            pending = []
    except Exception:
        pending = []
    pending.append({
        "id": f"memory-{datetime.now().strftime('%Y%m%d%H%M%S')}-{safe_title}",
        "title": title,
        "suggestion": suggestion,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
    })
    pending_path.write_text(json.dumps(pending, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n🧠 团队记忆建议（尚未写入 team_memory.md）")
    print(suggestion)
    print(f"待确认记录：{pending_path}")
    print("请选择：")
    print("1. 写入 knowledge/team_memory.md")
    print("2. 暂不写入")
    print("3. 修改后再写入")
    return 0

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_json")
    parser.add_argument("--workspace", help="工作区根目录（显式指定，可规避自动检测歧义）")
    args = parser.parse_args()

    try:
        json_path = Path(args.input_json).resolve()
        json_dir = json_path.parent

        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Resolve source_file relative to JSON file's directory (not cwd),
        # so callers can use bare filenames like "02_Draft.md" when JSON sits next to the project.
        raw_source = data.get('source_file', '')
        if raw_source:
            source_path = Path(raw_source)
            if not source_path.is_absolute():
                data['source_file'] = str(json_dir / source_path)
            # else: absolute path — use as-is
        if data.get('workspace_root') and not Path(data['workspace_root']).is_absolute():
            data['workspace_root'] = str(json_dir / data['workspace_root'])

        return process_archive(data, explicit_workspace=args.workspace)
    except Exception as e:
        print(f"Error: {e}")
        return 1

if __name__ == "__main__":
    raise SystemExit(main())

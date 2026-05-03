#!/usr/bin/env python3
import json
import argparse
import shutil
import re
import subprocess
from pathlib import Path
from datetime import datetime

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
    """Get the real Obsidian vault root by looking for the .obsidian configuration folder."""
    if start_path is None:
        start_path = Path(__file__).resolve()
    
    current = start_path
    while current.parent != current:
        if (current / ".obsidian").is_dir():
            return current
        current = current.parent
    
    # Fallback: Assume repo root is vault root
    return get_workspace_root().resolve()

def get_obsidian_path(abs_path):
    """Convert absolute path to vault-relative path for Obsidian CLI."""
    # Obsidian CLI expects paths RELATIVE to the REAL vault root.
    vault_root = get_obsidian_vault_root()
    try:
        # Ensure we are working with absolute resolved paths
        target_path = Path(abs_path).resolve()
        rel_path = target_path.relative_to(vault_root)
        return str(rel_path)
    except ValueError:
        # If path is not under vault_root, return as is (Obsidian will likely fail anyway)
        return str(abs_path)

def is_obsidian_reachable(file_path):
    """Check if a file path is located within the current Obsidian vault."""
    vault_root = get_obsidian_vault_root()
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
            print(f"⚠️ CLI Property set failed for {key}: {err}")
            
    return success_count == total_props # Only return True if ALL succeeded

def obsidian_move(src, dest):
    """Move a file using Obsidian CLI to preserve links."""
    src_rel = get_obsidian_path(src)
    dest_rel = get_obsidian_path(dest)
    
    # Use Obsidian 1.12 syntax: move path=... to=...
    ok, err = run_obsidian_cmd(["move", f"path={src_rel}", f"to={dest_rel}"])
    if not ok:
        print(f"⚠️ CLI Move failed: {err}")
    return ok

def get_workspace_root():
    # scripts -> wechat-writer -> Skills -> [RepoRoot] -> parent (contains David-Writing-Team and conductor)
    # After open-source rename, repo root still has same structure (Skills/ + conductor/)
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent.parent.parent  # Skills/wechat-writer/ -> Skills/ -> repo root
    return repo_root.parent  # parent containing both the repo dir and conductor/

def get_knowledge_dir():
    # knowledge/ is at Skills/wechat-writer/knowledge (relative to repo root)
    skill_root = Path(__file__).resolve().parent.parent  # wechat-writer/
    return skill_root / "knowledge"

def sanitize_filename(name):
    return re.sub(r'[<>:"/\\|?*]', '', name).strip()

def yaml_escape(value):
    """Escape text for YAML double-quoted string values."""
    text = "" if value is None else str(value)
    return text.replace("\\", "\\\\").replace('"', '\\"')

def to_vault_path(path_value, vault_dir_name):
    """Normalize path into vault-root based relative path.

    Example: published/img/cover-main.jpg -> Wechat/published/img/cover-main.jpg
    """
    raw = "" if path_value is None else str(path_value).strip()
    if not raw:
        return ""

    normalized = raw.replace("\\", "/").lstrip("/")

    # Keep explicit URL-like values untouched.
    if "://" in normalized:
        return normalized

    prefix = f"{vault_dir_name}/"
    if normalized.startswith(prefix):
        return normalized

    return f"{prefix}{normalized}"

def pick_cover_image(img_dir):
    """Pick cover image from archived image folder.

    Priority:
    1. Exact match: cover-combined.jpg
    2. Exact match: cover-main.jpg
    3. Partial match: *cover-combined*
    4. Partial match: *cover-main*
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
    image_exts = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    image_files = sorted(
        [
            p for p in img_dir.iterdir()
            if p.is_file() and p.suffix.lower() in image_exts
        ],
        key=lambda p: p.name.lower()
    )

    if not image_files:
        return None

    priorities = ("cover-combined", "cover-main")
    for keyword in priorities:
        for file_path in image_files:
            if keyword in file_path.name.lower():
                return file_path

    return None

def update_index(title, excerpt, filename):
    """
    更新 published_article_index.md
    - title: 文章标题（用于 Obsidian Wiki Link 和显示）
    - excerpt: 摘要
    - filename: 实际保存的文件名（不含扩展名），暂不使用
    """
    index_path = get_knowledge_dir() / "published_article_index.md"
    if not index_path.exists():
        print(f"Warning: Index file {index_path} not found.")
        return

    # Obsidian Wiki Link: 使用纯标题格式 [[标题]]
    link = f"[[{title}]]"

    line = f"| {link} | {excerpt} |"
    month_header = f"## {datetime.now().strftime('%Y-%m')}"

    try:
        content = index_path.read_text(encoding='utf-8')
        # Avoid duplicates (can happen if index update logic changes or a rerun occurs).
        if link in content:
            print(f"Index already contains entry: {link}")
            return

        lines = content.splitlines()

        if month_header not in content:
            # Create new month section at the TOP (before first existing month)
            # Find the first '## YYYY-MM' line (month header)
            insert_pos = 0
            for i, l in enumerate(lines):
                if l.strip().startswith('## 20'):  # Match '## 2025-xx' or '## 2026-xx'
                    insert_pos = i
                    break

            new_section = f"\n{month_header}\n\n| 标题 | 摘要 |\n| --- | --- |\n{line}\n"
            lines.insert(insert_pos, new_section)
            index_path.write_text('\n'.join(lines), encoding='utf-8')
            print(f"Created new month section at top: {index_path}")
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
                        return

            # If header found but table structure not found (rare), append in-place under the header.
            with index_path.open('a', encoding='utf-8') as f:
                 f.write(f"\n{line}\n")

    except Exception as e:
        print(f"Error updating index: {e}")

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
            # 或者，只要确认是元数据块，就删除引用块部分。
            # 按照 io_schema，Draft 头部通常有 ---。
            # 这里采取激进但基于内容的策略：只要确认是元数据块，就删除到当前位置。
            delete_end_index = j
            break

    return '\n'.join(lines[delete_end_index:])

def process_archive(data):
    source_file = Path(data.get('source_file', ''))
    fm = data.get('frontmatter', {})

    # --- Security Validation (Move to top) ---
    # Ensure source file is inside 'To-be-used/Project_*' before reading/writing anything.
    workspace_root = get_workspace_root()
    workspace_name = workspace_root.name

    if source_file.exists():
        project_dir = source_file.parent
        allowed_parent = (workspace_root / "To-be-used").resolve()
        try:
            current_parent = project_dir.parent.resolve()
        except Exception:
             current_parent = None

        if current_parent != allowed_parent:
             print(f"⚠️ Security Violation: Source file is in '{current_parent}', but must be in '{allowed_parent}' to be archived.")
             print("   Operation aborted to prevent unauthorized access or data loss.")
             return
    else:
        # If file doesn't exist, we can't validate its path context properly relative to Project dir,
        # but the script later handles non-existent files.
        # However, for safety, let's just warn if we can't determine context.
        pass

    title = fm.get('title', 'Untitled')
    safe_title = sanitize_filename(title)
    
    workspace_root = get_workspace_root()
    target_dir = workspace_root / "published"
    target_dir.mkdir(parents=True, exist_ok=True)
    
    target_file = target_dir / f"{safe_title}.md"
    
    # Read & Clean
    if source_file.exists():
        content = source_file.read_text(encoding='utf-8')
        content = strip_frontmatter(content)
        content = strip_h1_title(content)
        content = strip_draft_metadata(content)
    else:
        content = ""
        print(f"Warning: Source file {source_file} not found. Creating empty published file.")

    # Move img/ folder to published/ and resolve cover path.
    # Keep explicit cover if provided by upstream input.
    cover_path = to_vault_path(fm.get('cover', ''), workspace_name)
    excerpt = "" if fm.get('excerpt') is None else str(fm.get('excerpt')).strip()
    if len(excerpt) > 120:
        print(f"⚠️ Excerpt length is {len(excerpt)} (>120). Please shorten it in Stage 3.")
    if source_file.exists():
        project_dir = source_file.parent
        img_dir = project_dir / "img"

        if img_dir.exists() and img_dir.is_dir():
            # Keep fixed output directory name for plugin config compatibility.
            img_dest = target_dir / "img"

            try:
                # Preserve previous published/img if present, then replace with new one.
                if img_dest.exists():
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    backup = target_dir / f"img_prev_{timestamp}"
                    counter = 1
                    while backup.exists():
                        backup = target_dir / f"img_prev_{timestamp}_{counter}"
                        counter += 1
                    shutil.move(str(img_dest), str(backup))
                    print(f"📦 Existing published/img moved to backup: {backup}")

                shutil.move(str(img_dir), str(img_dest))
                print(f"🖼️  Moved images to: {img_dest}")

                # Auto-pick only when cover was not explicitly provided.
                if not cover_path:
                    cover_file = pick_cover_image(img_dest)
                    if cover_file:
                        relative_path = cover_file.relative_to(workspace_root).as_posix()
                        cover_path = to_vault_path(relative_path, workspace_name)
                        print(f"🖼️  Cover selected: {cover_path}")
                    else:
                        print("⚠️ No cover-combined/cover-main found. cover stays empty.")
                else:
                    print(f"ℹ️ Keep explicit cover from input: {cover_path}")
            except Exception as e:
                # Non-blocking: publish text first even if image move fails.
                print(f"⚠️ Image archive failed, continue without auto cover: {e}")
    
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
        new_content = f"""---
title: "{yaml_escape(title)}"
date: "{props['date']}"
slug: "{yaml_escape(props['slug'])}"
excerpt: "{yaml_escape(props['excerpt'])}"
cover: "{yaml_escape(props['cover'])}"
tags: {json.dumps(props['tags'])}
status: published
---
{content}"""
        target_file.write_text(new_content, encoding='utf-8')
        if cli_ok:
            print(f"🚀 Published article to: {target_file} (Fallback-Mode)")
        else:
            print(f"🚀 Published article to: {target_file} (Legacy-Mode)")
    
    # Update Index
    # Pass filename (without extension) for Obsidian Wiki Link
    update_index(title, excerpt, safe_title)

    # Archive Project Folder
    if source_file.exists():
        project_dir = source_file.parent

        # Safety: only move well-formed project folders.
        if "Project_" in project_dir.name:
            archive_base = workspace_root / "conductor" / "archive"
            archive_base.mkdir(parents=True, exist_ok=True)

            today = datetime.now().strftime('%Y%m%d')
            # Strip 'Project_' prefix (case-insensitive) for cleaner archive name
            clean_name = re.sub(r'^project_', '', project_dir.name, flags=re.IGNORECASE)
            archive_dest = archive_base / f"{today}_{sanitize_filename(clean_name)}"

            # Handle name collision by adding suffix
            if archive_dest.exists():
                counter = 1
                while archive_dest.exists():
                    archive_dest = archive_base / f"{today}_{sanitize_filename(clean_name)}_{counter}"
                    counter += 1

            # Use Obsidian CLI move to preserve links if available
            if cli_ok and is_obsidian_reachable(project_dir):
                # IMPORTANT: Move folder via CLI file-by-file since CLI only supports file moves
                print(f"📦 Archiving project via CLI: {project_dir.name} -> {archive_dest.name}")
                archive_dest.mkdir(parents=True, exist_ok=True)
                
                cli_success = True
                for item in project_dir.rglob('*'):
                    if item.is_file():
                        rel_path = item.relative_to(project_dir)
                        target_item = archive_dest / rel_path
                        target_item.parent.mkdir(parents=True, exist_ok=True)
                        if not obsidian_move(item, target_item):
                            cli_success = False
                            # Fallback for individual file if CLI fails
                            shutil.move(str(item), str(target_item))
                
                if cli_success:
                    print(f"📦 Archived project to: {archive_dest} (CLI-Native)")
                else:
                    print(f"📦 Archived project to: {archive_dest} (Partial CLI/Fallback)")
                
                # Cleanup source directory
                try:
                    shutil.rmtree(str(project_dir))
                except Exception as e:
                    print(f"⚠️ Failed to remove source folder after move: {e}")
            else:
                shutil.move(str(project_dir), str(archive_dest))
                print(f"📦 Archived project to: {archive_dest} (Legacy-Mode)")
        elif project_dir.name == "To-be-used":
            # Inside To-be-used but not in a Project folder
            print("⚠️ Source file not in 'Project_*' folder, skipping project archive.")
        else:
            print("⚠️ Source file not in 'To-be-used' or 'Project_*' folder, skipping project archive.")
        
    # Memory Suggestion
    print("\n🧠 **Memory Suggestion** (Please update knowledge/team_memory.md):")
    print(f"- [{datetime.now().strftime('%Y-%m-%d')}] [Experience] Completed {title}.")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_json")
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

        process_archive(data)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""WeChat Director —— Storyboard 解析器。"""
import re
from pathlib import Path

from director_core import (ASPECT_RATIOS, check_ip_requirement, clean_prompt,
                           sanitize_filename)

def extract_context(text_block):
    match = re.search(r'>\s*Context\s*[:：]\s*["“](.*?)["”]', text_block, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    match = re.search(r'>\s*Context\s*[:：]\s*(.+)', text_block, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def parse_visual_brief(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Base title from filename
    filename_title = sanitize_filename(Path(file_path).stem)
    title = filename_title

    # 2. Fallback: If filename is generic "Storyboard", use parent directory name (Project Name)
    if title.lower() == "storyboard":
        parent_dir = Path(file_path).parent.name
        if parent_dir:
            title = sanitize_filename(parent_dir)

    # 3. Override: Explicit frontmatter title has highest priority
    fm_match = re.search(r'^title:\s*"(.+?)"', content, re.MULTILINE)
    if fm_match:
        title = sanitize_filename(fm_match.group(1))

    tasks = []

    # 1. Main Cover
    if "cover-main" in content or "主视觉" in content:
        section_match = re.search(r'###\s*Part\s*A[:：][^\n]*主视觉.*?(?=###\s*Part\s*B|##|\Z)', content, re.DOTALL | re.IGNORECASE)
        if section_match:
            section_text = section_match.group(0)
            prompt_match = re.search(r'```(?:\w+)?\n(.*?)```', section_text, re.DOTALL)
            if prompt_match:
                prompt = clean_prompt(prompt_match.group(1))
                if prompt:
                    dims = ASPECT_RATIOS["cover-main"]
                    tasks.append({
                        "type": "cover-main", "prompt": prompt,
                        "width": dims["width"], "height": dims["height"],
                        "suffix": "cover-main",
                        "use_ip": check_ip_requirement(section_text),
                        "context": None
                    })

    # 2. Sidebar Cover
    if "cover-sidebar" in content or "侧边栏" in content:
        section_match = re.search(r'###\s*Part\s*B[:：][^\n]*侧边栏.*?(?=##|\Z)', content, re.DOTALL | re.IGNORECASE)
        if section_match:
            section_text = section_match.group(0)
            prompt_match = re.search(r'```(?:\w+)?\n(.*?)```', section_text, re.DOTALL)
            if prompt_match:
                prompt = clean_prompt(prompt_match.group(1))
                if prompt:
                    dims = ASPECT_RATIOS["cover-sidebar"]
                    tasks.append({
                        "type": "cover-sidebar", "prompt": prompt,
                        "width": dims["width"], "height": dims["height"],
                        "suffix": "cover-sidebar",
                        "use_ip": check_ip_requirement(section_text),
                        "context": None
                    })

    # 3. In-article Illustrations
    illustration_count = 0
    for match in re.finditer(r'###\s*Part\s*C[:：][^\n]*内文配图.*?(?=###\s*Part\s*[A-Z]|\Z)', content, re.DOTALL | re.IGNORECASE):
        section_text = match.group(0)
        for block in re.finditer(r'####\s*插图\s*\d+.*?(?=####\s*插图|##|\Z)', section_text, re.DOTALL):
            block_text = block.group(0)

            # Extract Description
            desc_match = re.match(r'####\s*插图\s*\d+[:：]?\s*(.*)', block_text)
            description = ""
            if desc_match:
                description = re.sub(r'[<>:"/\\|?*]', '', desc_match.group(1)).strip()

            prompt_match = re.search(r'```(?:\w+)?\n(.*?)```', block_text, re.DOTALL)
            if not prompt_match: continue

            prompt = clean_prompt(prompt_match.group(1))
            if not prompt: continue

            illustration_count += 1
            dims = ASPECT_RATIOS["illustration"]
            context = extract_context(block_text)

            tasks.append({
                "type": "illustration",
                "prompt": prompt,
                "width": dims["width"],
                "height": dims["height"],
                "suffix": f"illustration-{illustration_count:02d}",
                "use_ip": check_ip_requirement(block_text),
                "context": context,
                "description": description
            })

    return title, tasks

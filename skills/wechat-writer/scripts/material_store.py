#!/usr/bin/env python3
"""Store user-confirmed material or Seed content in the selected workspace location.

This script never decides whether content is worth saving. The Agent must show
the confirmation card first and call it only after the user chooses a target.
"""

import argparse
import hashlib
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from console_encoding import configure_console

configure_console()


def safe_name(value):
    return "".join(ch for ch in value.strip() if ch not in '<>:"/\\|?*').strip()


def store_material(workspace, destination, content, project=None, topic=None):
    root = Path(workspace).resolve()
    if not (root / "articles").is_dir():
        raise ValueError(f"Not a WechatWrite workspace: {root}")
    text = content.strip()
    if not text:
        raise ValueError("content is empty")

    if destination == "material":
        target = root / "knowledge" / "素材库.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        fingerprint = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        existing = target.read_text(encoding="utf-8") if target.exists() else ""
        if f"<!-- material:{fingerprint} -->" in existing:
            raise FileExistsError(f"Duplicate material: {fingerprint}")
        with target.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(f"\n---\n<!-- material:{fingerprint} -->\n### 📅 {date.today().isoformat()}\n{text}\n")
        return target

    if destination == "project-seed":
        if not project:
            raise ValueError("project is required for project-seed")
        project_dir = root / "articles" / f"Project_{safe_name(project)}"
        if not project_dir.is_dir():
            raise FileNotFoundError(
                f"Project does not exist: {project_dir}. Choose an existing project or create it first."
            )
        target_dir = project_dir / "_source" / "Seeds"
    elif destination == "long-term-seed":
        target_dir = root / "knowledge" / "seeds"
    else:
        raise ValueError(f"unknown destination: {destination}")
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = safe_name(topic or "Imported") or "Imported"
    target = target_dir / f"Seed_{filename}.md"
    if target.exists():
        raise FileExistsError(f"Seed already exists: {target}")
    target.write_text(
        "---\n"
        f"title: {filename}\n"
        f"created: {date.today().isoformat()}\n"
        f"source: user-confirmed\n"
        "---\n\n"
        f"{text}\n",
        encoding="utf-8",
    )
    return target


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--destination", choices=("material", "project-seed", "long-term-seed"), required=True)
    parser.add_argument("--content", required=True)
    parser.add_argument("--project")
    parser.add_argument("--topic")
    args = parser.parse_args()
    try:
        target = store_material(args.workspace, args.destination, args.content, args.project, args.topic)
        print(f"Saved: {target}")
        return 0
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Apply a user-confirmed pending team-memory suggestion."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from console_encoding import configure_console

configure_console()


def apply_memory(workspace, suggestion_id, action, text=None):
    root = Path(workspace).resolve()
    pending_path = root / "conductor" / "pending_memory_suggestions.json"
    memory_path = root / "knowledge" / "team_memory.md"
    if not pending_path.exists():
        raise FileNotFoundError(f"No pending memory file: {pending_path}")
    try:
        pending = json.loads(pending_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("Pending memory file is unreadable; original file preserved") from exc
    if not isinstance(pending, list) or any(not isinstance(item, dict) for item in pending):
        raise ValueError("Pending memory must be a list of objects; original file preserved")
    match = next((item for item in pending if item.get("id") == suggestion_id and item.get("status") == "pending"), None)
    if match is None:
        raise ValueError(f"Pending suggestion not found: {suggestion_id}")
    if action in {"accept", "edit"} and not isinstance(text or match.get("suggestion"), str):
        raise ValueError("Memory suggestion must contain text")
    if action == "accept":
        memory_path.parent.mkdir(parents=True, exist_ok=True)
        with memory_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write("\n" + (text or match["suggestion"]) + "\n")
    elif action == "edit":
        if not text or not text.strip():
            raise ValueError("--text is required for edit")
        memory_path.parent.mkdir(parents=True, exist_ok=True)
        with memory_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write("\n" + text.strip() + "\n")
    elif action not in {"dismiss"}:
        raise ValueError(f"Unknown action: {action}")
    match["status"] = "accepted" if action in {"accept", "edit"} else "dismissed"
    pending_path.write_text(json.dumps(pending, ensure_ascii=False, indent=2), encoding="utf-8")
    return memory_path if action in {"accept", "edit"} else pending_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--id", required=True)
    parser.add_argument("--action", choices=("accept", "dismiss", "edit"), required=True)
    parser.add_argument("--text")
    args = parser.parse_args()
    try:
        print(f"Updated: {apply_memory(args.workspace, args.id, args.action, args.text)}")
        return 0
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

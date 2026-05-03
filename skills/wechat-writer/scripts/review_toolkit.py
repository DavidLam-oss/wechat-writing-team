#!/usr/bin/env python3
"""
review_toolkit.py - 文章审校报告渲染工具

纯渲染工具：将 JSON 格式的审校报告渲染为 Markdown。

用法:
  python3 review_toolkit.py --mode critique /path/to/_temp_critique.json
  python3 review_toolkit.py --mode directive /path/to/_temp_directive.json
  python3 review_toolkit.py --mode feedback /path/to/_temp_feedback.json

注意：
  - JSON 文件由调用方（Agent）生成，本脚本只负责渲染。
  - 在 OpenClaw 服务端：由主 Agent（罗永浩）生成 JSON 后调用本脚本。
  - 在本地（Claude Code / Codex / Gemini CLI）：人工生成 JSON 或由主 Agent 生成。
"""
import json
import argparse
import sys
from pathlib import Path
from datetime import datetime


# ==================== 渲染函数 ====================

def clean_text(text):
    if not isinstance(text, str):
        return str(text)
    return text.replace('\n', ' ').strip()


def render_markdown_file(lines, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        output_path.write_text('\n'.join(lines), encoding='utf-8')
        print(f"Successfully generated: {output_path}", file=sys.stderr)
    except IOError as e:
        print(f"Error writing output file: {e}", file=sys.stderr)


def append_review_section(md, title, data):
    if not data:
        return

    md.append(f"#### {title}")
    status = data.get('status')
    score = data.get('score')
    if status or score is not None:
        summary = []
        if status:
            summary.append(f"状态: {clean_text(status)}")
        if score is not None:
            summary.append(f"评分: {score}")
        md.append(f"**{' / '.join(summary)}**")

    evidence = data.get('evidence', [])
    if evidence:
        md.append(f"| 发现项 |")
        md.append(f"| :--- |")
        for item in evidence:
            md.append(f"| {clean_text(str(item))} |")

    priorities = data.get('priorities', [])
    if priorities:
        md.append("")
        md.append("**优先返工项**:")
        for item in priorities:
            md.append(f"- {clean_text(str(item))}")

    md.append("")


def render_critique(data, output_path):
    md = []
    source_file = clean_text(data.get('source_file', 'Unknown'))
    meta = data.get('meta', {})
    score = meta.get('score', 0)
    verdict = meta.get('verdict', 'Unknown')
    persona = clean_text(data.get('critic_persona', 'The Critic'))

    verdict_emoji = "🟢" if verdict == "Pass" else "🔴"
    if verdict == "Needs Work":
        verdict_emoji = "🟡"

    md.append(f"### 🛑 毒舌体检报告 (Toxic Critique)")
    md.append(f"")
    md.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    md.append(f"**体检医生**: {persona}")
    md.append(f"**被审对象**: `{Path(source_file).name}`")
    md.append(f"**综合评分**: `{score}/100`")
    md.append(f"**最终裁决**: {verdict_emoji} **{verdict}**")
    md.append(f"")
    md.append(f"---")
    md.append(f"")

    points = data.get('critique_points', {})

    logic = points.get('logic_flaws', [])
    if logic:
        md.append(f"#### 1. 逻辑漏洞 (Logic)")
        for item in logic:
            severity = "🔥🔥🔥" if item.get('severity') == 'High' else ("🔥🔥" if item.get('severity') == 'Medium' else "🔥")
            md.append(f"* {severity} **{clean_text(item.get('point', ''))}**")
        md.append("")

    ai_smell = points.get('ai_smell', {})
    if ai_smell:
        md.append(f"#### 2. AI味检测 (Anti-AI)")
        md.append(f"**自然度评分**: {ai_smell.get('score', 'N/A')}")
        evidence = ai_smell.get('evidence', [])
        if evidence:
            md.append(f"| 发现项 |")
            md.append(f"| :--- |")
            for ev in evidence:
                md.append(f"| {clean_text(str(ev))} |")
        md.append("")

    append_review_section(md, "3. 内容成立度 (L3)", points.get('content_depth', {}))
    append_review_section(md, "4. 老友感终审 (L4)", points.get('david_layer', {}))

    md.append(f"---")
    md.append(f"**老罗总评**: {clean_text(data.get('overall_comment', ''))}")

    render_markdown_file(md, output_path)


def render_directive(data, output_path):
    lines = []
    lines.append(f"# 综改指令: {data.get('title', 'Unknown Title')}")
    lines.append(f"> **Status**: {data.get('status', 'PENDING')}")

    if data.get('conflict_resolution', {}).get('has_conflict'):
        lines.append(f"\n## ⚠️ 冲突待决\n> {data['conflict_resolution'].get('details')}\n\n**请大卫裁决。**")
    else:
        lines.append("\n## 1. 综合反馈 (Consolidated Feedback)")
        for item in data.get('critique_summary', []):
            lines.append(f"- **[{item.get('source', '')}]**: {item.get('point', '')}")
            lines.append(f"  - -> *Action*: {item.get('action', '')}")

        lines.append("\n## 2. 主编建议 (Editorial Suggestions)")
        for item in data.get('editorial_suggestions', []):
            lines.append(f"1. **原句**: `{item.get('original', '')}`")
            lines.append(f"   **建议**: `{item.get('suggestion', '')}`")

    lines.append("\n---\n**指令下达人**: 主编 (Main Editor)")
    render_markdown_file(lines, output_path)


def render_feedback(data, output_path):
    md = []
    md.append(f"### 📖 路人试读报告 (User Feedback)")
    verdict = data.get('overall_verdict', 'Unknown')
    md.append(f"**最终态度**: {'🟢' if verdict=='Pass' else '🔴'} **{verdict}**")

    tests = data.get('tests', {})

    click = tests.get('click_test', {})
    md.append(f"#### 1. 3秒钩子")
    md.append(f"* **决策**: {click.get('decision', '')} - {click.get('reason', '')}")

    finish = tests.get('finish_test', {})
    md.append(f"#### 2. 完读率")
    md.append(f"* **决策**: {finish.get('decision', '')}")
    if finish.get('drop_point'):
        md.append(f"* **流失点**: {finish.get('drop_point')}")

    md.append(f"---")
    md.append(f"**最戳我的一句**: \"{data.get('best_quote', '')}\"")

    render_markdown_file(md, output_path)


# ==================== Main ====================

def main():
    parser = argparse.ArgumentParser(
        description="review_toolkit.py - 文章审校报告渲染工具（纯渲染，不含 LLM 调用）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 review_toolkit.py --mode critique /path/to/_temp_critique.json
  python3 review_toolkit.py --mode directive /path/to/_temp_directive.json
  python3 review_toolkit.py --mode feedback /path/to/_temp_feedback.json

JSON 由调用方生成，详见 SKILL.md 中各角色职责说明。
"""
    )
    parser.add_argument("--mode", required=True, choices=['critique', 'directive', 'feedback'], help="报告类型")
    parser.add_argument("input_json", help="输入 JSON 文件路径")

    args = parser.parse_args()

    path = Path(args.input_json)
    if not path.exists():
        print(f"Error: JSON 文件不存在: {path}", file=sys.stderr)
        sys.exit(1)

    with path.open('r', encoding='utf-8') as f:
        data = json.load(f)

    stem = path.stem
    for p in ['_temp_', 'temp_', 'critique_', 'directive_', 'feedback_']:
        if stem.startswith(p):
            stem = stem[len(p):]
            break

    if args.mode == 'critique':
        out_name = f"[Critique_Report]{stem}.md"
        render_critique(data, path.parent / out_name)
    elif args.mode == 'directive':
        out_name = f"Directive_{stem}.md"
        render_directive(data, path.parent / out_name)
    elif args.mode == 'feedback':
        out_name = f"[User_Feedback]{stem}.md"
        render_feedback(data, path.parent / out_name)


if __name__ == "__main__":
    main()

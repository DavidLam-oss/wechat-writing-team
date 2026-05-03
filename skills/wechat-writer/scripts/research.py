#!/usr/bin/env python3
import json
import argparse
from pathlib import Path
from datetime import datetime

def clean_text(text):
    if not isinstance(text, str): return str(text)
    return text.replace('\n', ' ').strip()

def escape_table_cell(text):
    text = clean_text(text)
    text = text.replace('|', '\\|')
    return text

def normalize_verdict(verdict):
    mapping = {
        "Verified": "[验证通过]",
        "Correction": "[需修正]",
        "Unverified": "[存疑/未找到]",
        "Verified (Corrected)": "[需修正]"
    }
    return mapping.get(verdict, f"[{verdict}]")

def render_markdown(data, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)

    md = []
    md.append(f"### 📚 调研报告 (Research Report)")
    md.append(f"")
    
    gen_time = datetime.now().strftime('%Y-%m-%d %H:%M')
    md.append(f"**生成时间**: {gen_time}")
    md.append(f"---")
    md.append(f"")

    # Content
    data_content = data.get('data', {})
    
    # Fact Check
    fact_checks = data_content.get('fact_checks', [])
    if fact_checks:
        md.append(f"#### 🔍 1. 数据验证 (Fact Check)")
        md.append(f"| 原文表述 | 验证结果 | 来源 & 备注 |")
        md.append(f"| :--- | :--- | :--- |")
        for item in fact_checks:
            claim = escape_table_cell(item.get('claim', ''))
            verdict_raw = item.get('verdict', 'Unverified')
            verdict_norm = normalize_verdict(verdict_raw)
            truth = escape_table_cell(item.get('truth', ''))
            source = item.get('source', '')
            
            verdict_fmt = f"**{verdict_norm}**"
            # Only add truth if it's a correction. 
            # Logic: If it's NOT "Verified" (or equivalent), show truth.
            if "Verified" not in verdict_raw and "验证通过" not in verdict_norm: 
                if truth: verdict_fmt += f" {truth}"
            
            md.append(f"| {claim} | {verdict_fmt} | {escape_table_cell(source)} |")
        md.append(f"")

    try:
        output_path.write_text('\n'.join(md), encoding='utf-8')
        print(f"Successfully generated report at: {output_path}")
    except IOError as e:
        print(f"Error writing output file: {e}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_json")
    args = parser.parse_args()

    input_path = Path(args.input_json)
    if not input_path.exists(): return

    try:
        with input_path.open('r', encoding='utf-8') as f:
            data = json.load(f)

        output_filename = "Research_Report.md"
        # Always output to the same directory as input json (Project Dir)
        output_path = input_path.parent / output_filename
        
        render_markdown(data, output_path)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()

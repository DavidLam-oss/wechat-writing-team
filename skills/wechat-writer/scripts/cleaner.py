#!/usr/bin/env python3
import json
import argparse
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent))
from console_encoding import configure_console

configure_console()

def save_markdown(data, output_path):
    """
    Saves the cleaned content with standard frontmatter.
    """
    content = data.get('cleaned_content', '')
    source_file = data.get('source_file', 'Unknown')
    # meta = data.get('meta', {}) # Optional meta

    # Construct Frontmatter
    lines = []
    lines.append("---")
    lines.append(f"source_file: {source_file}")
    lines.append(f"status: Cleaned")
    lines.append(f"created: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("---")
    lines.append("")
    lines.append("# Cleaned Source")
    lines.append(content)

    # Write to file
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text('\n'.join(lines), encoding='utf-8')
        print(f"Successfully saved cleaned text to: {output_path}")
        return True
    except IOError as e:
        print(f"Error writing output file: {e}", file=sys.stderr)
        return False

def main():
    parser = argparse.ArgumentParser(description="Save Cleaned Text from JSON")
    parser.add_argument("input_json", help="Path to the input JSON file")
    args = parser.parse_args()

    input_path = Path(args.input_json)
    if not input_path.exists():
        print(f"Error: Input file '{input_path}' not found.")
        return 1

    try:
        with input_path.open('r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("cleaning JSON must be an object")

        source_file_path = Path(data.get('source_file', 'Raw_Material.txt'))
        
        # Logic: Save to the same directory as the source file (Project Dir)
        # If source file is just a filename, assume current dir? 
        # Ideally, we put it in the Project Dir. 
        # If the input JSON is generated in the Project Dir, we can use that.
        
        # Assumption: The Agent runs this script knowing the input JSON is in the working context.
        # We will iterate to find a good output name.
        
        stem = source_file_path.stem
        # Remove prefixes
        for prefix in ['Raw_', 'Cleaned_', 'Draft_']:
            if stem.startswith(prefix):
                stem = stem[len(prefix):]
        
        output_filename = f"Cleaned_{stem}.md"
        
        # Use input_json parent as the base for output, assuming input_json is in the project dir.
        output_path = input_path.parent / output_filename
        
        return 0 if save_markdown(data, output_path) else 1

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())

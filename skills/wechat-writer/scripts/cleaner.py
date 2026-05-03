#!/usr/bin/env python3
import json
import argparse
from pathlib import Path
from datetime import datetime

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
    lines.append(f"# Cleaned Source\n")
    lines.append(content)

    # Write to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        output_path.write_text('\n'.join(lines), encoding='utf-8')
        print(f"Successfully saved cleaned text to: {output_path}")
    except IOError as e:
        print(f"Error writing output file: {e}")

def main():
    parser = argparse.ArgumentParser(description="Save Cleaned Text from JSON")
    parser.add_argument("input_json", help="Path to the input JSON file")
    args = parser.parse_args()

    input_path = Path(args.input_json)
    if not input_path.exists():
        print(f"Error: Input file '{input_path}' not found.")
        return

    try:
        with input_path.open('r', encoding='utf-8') as f:
            data = json.load(f)

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
        
        save_markdown(data, output_path)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()

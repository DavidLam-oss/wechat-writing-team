#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
WeChat HTML to Markdown Exporter
Converts raw HTML downloaded from WeChat into preserved Markdown formats with YAML frontmatter.
"""

import os
import sys
import re
import json
import logging
from typing import Dict, Optional

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("md_exporter")

# Import third-party dependencies with user-friendly error messages
try:
    from bs4 import BeautifulSoup
except ImportError:
    logger.error("Required package 'beautifulsoup4' is not installed. Please run: pip3 install beautifulsoup4")
    sys.exit(1)

try:
    import html2text
except ImportError:
    logger.error("Required package 'html2text' is not installed. Please run: pip3 install html2text")
    sys.exit(1)


def parse_metadata_fallback(html_soup: BeautifulSoup, url: str = "") -> Dict[str, str]:
    """
    Fallback metadata parser directly using BeautifulSoup.
    """
    meta = {
        "title": "Untitled Article",
        "author": "Unknown Author",
        "source_url": url,
        "fetched_at": ""
    }

    # Title
    og_title = html_soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        meta["title"] = og_title.get("content").strip()
    else:
        title_h1 = html_soup.find("h1", id="activity-name")
        if title_h1:
            meta["title"] = title_h1.get_text().strip()

    # Author
    og_author = html_soup.find("meta", property="og:article:author")
    if og_author and og_author.get("content"):
        meta["author"] = og_author.get("content").strip()
    else:
        nickname_span = html_soup.find("span", class_="rich_media_meta_text")
        if nickname_span:
            meta["author"] = nickname_span.get_text().strip()

    # Source URL
    og_url = html_soup.find("meta", property="og:url")
    if og_url and og_url.get("content"):
        meta["source_url"] = og_url.get("content").strip()

    return meta


def extract_share_image_urls(html_content: str) -> list:
    """
    Extract CDN image URLs from window.picture_page_info_list in image-share template.
    """
    urls = []
    # Regex search for picture_page_info_list definition block
    match = re.search(r'window\.picture_page_info_list\s*=\s*(.+?\.slice\(0,\s*20\);|\[.+?\])', html_content, re.DOTALL)
    if match:
        block = match.group(1)
        # Find all occurrence of cdn_url
        cdn_urls = re.findall(r'cdn_url:\s*\'([^\'\s]+)\'', block)
        for url in cdn_urls:
            urls.append(url.replace('\\/', '/'))
    return urls


def convert_html_to_md(html_path: str, meta_path: Optional[str]) -> str:
    """
    Main logic to parse Raw HTML and convert to Markdown.
    """
    with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
        html_content = f.read()

    soup = BeautifulSoup(html_content, 'html.parser')

    # Load Metadata
    metadata = {}
    if meta_path and os.path.exists(meta_path):
        try:
            with open(meta_path, 'r', encoding='utf-8') as mf:
                metadata = json.load(mf)
        except Exception as e:
            logger.warning(f"Failed to read metadata file {meta_path}. Error: {e}")

    # Fallback if metadata is incomplete
    fallback_meta = parse_metadata_fallback(soup, metadata.get("source_url", ""))
    for k, v in fallback_meta.items():
        if k not in metadata or not metadata[k]:
            metadata[k] = v

    # Build YAML frontmatter
    frontmatter = "---\n"
    frontmatter += f"title: \"{metadata.get('title', 'Untitled Article')}\"\n"
    frontmatter += f"author: \"{metadata.get('author', 'Unknown Author')}\"\n"
    frontmatter += f"source_url: \"{metadata.get('source_url', '')}\"\n"
    frontmatter += f"fetched_at: \"{metadata.get('fetched_at', '')}\"\n"
    frontmatter += "---\n\n"

    # Find the core content nodes
    content_node = soup.find(id="js_content")
    text_share_node = soup.find(id="js_text_desc")
    image_share_node = soup.find(id="js_image_desc")

    core_html = ""

    if content_node:
        # Standard article layout
        # Clean unneeded tags inside core
        for bad_tag in content_node.find_all(["script", "style"]):
            bad_tag.decompose()
        # Clean display:none styles from js_content
        if content_node.has_attr("style"):
            style_str = content_node["style"]
            style_str = re.sub(r'display\s*:\s*none', '', style_str, flags=re.IGNORECASE)
            content_node["style"] = style_str
        
        # Check text length. If empty, fall back to title text
        text_content = content_node.get_text().strip()
        if not text_content:
            core_html = f"<p style='font-size:17px;line-height:1.6;'>{metadata.get('title')}</p>"
        else:
            core_html = str(content_node)

    elif text_share_node:
        # Text-share template
        # Extract title share from JS data if HTML tag is empty
        desc_text = text_share_node.get_text().strip()
        if not desc_text:
            qmtpl_match = re.search(r'window\.__QMTPL_SSR_DATA__\s*=\s*({.+?});', html_content, re.DOTALL)
            if qmtpl_match:
                try:
                    qmtpl_data = json.loads(qmtpl_match.group(1))
                    desc_text = qmtpl_data.get("title", "").replace('\n', '<br>')
                except Exception:
                    pass

        if not desc_text:
            text_match = re.search(r'var\s+TextContentNoEncode\s*=\s*window\.a_value_which_never_exists\s*\|\|\s*\'([^\']*)\'', html_content)
            if text_match:
                desc_text = text_match.group(1).replace('\n', '<br>')

        core_html = f"<p>{desc_text}</p>" if desc_text else f"<p>{metadata.get('title')}</p>"

    elif image_share_node:
        # Image-share template
        desc_text = image_share_node.get_text().strip()
        if not desc_text:
            qmtpl_match = re.search(r'window\.__QMTPL_SSR_DATA__\s*=\s*({.+?});', html_content, re.DOTALL)
            if qmtpl_match:
                try:
                    qmtpl_data = json.loads(qmtpl_match.group(1))
                    desc_text = qmtpl_data.get("desc", "").replace('\n', '<br>')
                except Exception:
                    pass
        
        # Extract picture cdn list
        img_urls = extract_share_image_urls(html_content)
        img_tags = "".join([f'<p><img src="{u}" alt="WeChat Share Image" /></p>' for u in img_urls])
        
        core_html = f"<p>{desc_text}</p>" if desc_text else ""
        core_html += img_tags

    else:
        # Fallback layout: write title and whatever remains in body
        core_html = f"<p>{metadata.get('title')}</p>"

    # Convert to Markdown using html2text
    h = html2text.HTML2Text()
    h.ignore_links = False
    h.ignore_images = False
    h.body_width = 0  # Do not wrap lines
    h.unicode_snob = True  # Keep Unicode characters
    h.images_to_alt = True

    markdown_body = h.handle(core_html)
    
    # Post-process markdown links and formatting if needed
    # Ensure images with empty alt tags but containing CDN urls render correctly
    return frontmatter + markdown_body


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Convert raw WeChat HTML files into Markdown.")
    parser.add_argument("--in", dest="in_dir", required=True, help="Input directory containing raw HTML files (html_raw/).")
    parser.add_argument("--out", dest="out_dir", required=True, help="Output directory where preserved Markdown files will be saved.")
    parser.add_argument("--meta", dest="meta_dir", help="Metadata directory containing json files (optional, default to sibling of html_raw/).")
    args = parser.parse_args()

    if not os.path.exists(args.in_dir):
        logger.error(f"Input directory does not exist: {args.in_dir}")
        sys.exit(1)

    os.makedirs(args.out_dir, exist_ok=True)

    # Resolve meta directory
    meta_dir = args.meta_dir
    if not meta_dir:
        # Guess parent path + 'meta/'
        parent = os.path.dirname(os.path.abspath(args.in_dir.rstrip('/')))
        meta_dir = os.path.join(parent, "meta")

    # List all raw HTML files
    html_files = [f for f in os.listdir(args.in_dir) if f.endswith('.html')]
    if not html_files:
        logger.info(f"No HTML files found in {args.in_dir}")
        sys.exit(0)

    logger.info(f"Found {len(html_files)} HTML files to convert.")

    success_count = 0
    for hf in html_files:
        stem = os.path.splitext(hf)[0]
        html_path = os.path.join(args.in_dir, hf)
        meta_path = os.path.join(meta_dir, f"{stem}.json") if os.path.exists(meta_dir) else None
        
        out_md_path = os.path.join(args.out_dir, f"{stem}.md")
        
        try:
            md_content = convert_html_to_md(html_path, meta_path)
            with open(out_md_path, 'w', encoding='utf-8') as f:
                f.write(md_content)
            success_count += 1
            logger.info(f"Converted: {hf} -> {stem}.md")
        except Exception as e:
            logger.error(f"Failed to convert {hf}. Error: {e}")

    logger.info(f"Conversion complete. Successfully converted {success_count}/{len(html_files)} files.")

if __name__ == "__main__":
    main()

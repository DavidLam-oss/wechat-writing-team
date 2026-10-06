#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
WeChat HTML Normalizer and Cleaner
Normalizes raw WeChat HTML into cleaner standalone HTML files.
Injects no-referrer metadata to bypass CDN image hotlinking block.
"""

import os
import sys
import re
import json
import logging
from typing import Dict, Optional

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("html_exporter")

# Import BeautifulSoup
try:
    from bs4 import BeautifulSoup
except ImportError:
    logger.error("Required package 'beautifulsoup4' is not installed. Please run: pip3 install beautifulsoup4")
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


def extract_js_object(html_content: str, variable_name: str) -> Optional[dict]:
    """
    Extracts a JSON object defined in JS using regex.
    """
    pattern = rf'{re.escape(variable_name)}\s*=\s*({{.+?}});'
    match = re.search(pattern, html_content, re.DOTALL)
    if match:
        try:
            # Basic cleanup to make JS object JSON parseable
            js_str = match.group(1)
            # Remove comments
            js_str = re.sub(r'//.*', '', js_str)
            # Quote unquoted keys (simple helper)
            js_str = re.sub(r'(\s*)([a-zA-Z0-9_]+)(\s*):', r'\1"\2"\3:', js_str)
            # Replace single quotes with double quotes
            js_str = js_str.replace("'", '"')
            return json.loads(js_str)
        except Exception:
            pass
    return None


def format_pub_time(unix_str: str) -> str:
    try:
        unix_time = int(unix_str)
        import time
        return time.strftime("%Y年%m月%d日 %H:%M", time.localtime(unix_time))
    except Exception:
        return ""


def clean_and_normalize_html(html_path: str, meta_path: Optional[str]) -> str:
    """
    Parses and cleans raw WeChat HTML, injecting no-referrer meta and rendering dynamic states.
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

    # 1. Inject <meta name="referrer" content="no-referrer"> to head
    head = soup.find("head")
    if not head:
        head = soup.new_tag("head")
        soup.insert(0, head)
    
    # Check for existing referrer metas and remove them
    for ref_meta in head.find_all("meta", attrs={"name": "referrer"}):
        ref_meta.decompose()
        
    referrer_meta = soup.new_tag("meta", attrs={"name": "referrer", "content": "no-referrer"})
    head.insert(0, referrer_meta)

    # 2. Decompose useless elements
    for selector in ["#js_top_ad_area", "#js_tags_preview_toast", "#content_bottom_area", "#js_pc_qr_code", "#wx_stream_article_slide_tip"]:
        element = soup.select_one(selector)
        if element:
            element.decompose()

    # Decompose all <script> elements
    for script_tag in soup.find_all("script"):
        script_tag.decompose()

    # 3. Clean #js_content display:none styles
    content_div = soup.find(id="js_content")
    if content_div:
        if content_div.has_attr("style"):
            style_str = content_div["style"]
            style_str = re.sub(r'display\s*:\s*none', '', style_str, flags=re.IGNORECASE)
            content_div["style"] = style_str.strip()

        # If body is completely empty, fallback title
        text_content = content_div.get_text().strip()
        if not text_content:
            title = metadata.get("title", "Untitled Article")
            content_div.append(BeautifulSoup(f'<p style="font-size:17px;line-height:1.6;white-space:pre-wrap;">{title}</p>', 'html.parser'))

    # 4. Render publish time
    pub_time_div = soup.find(id="publish_time")
    if pub_time_div:
        match_time = re.search(r'var\s+oriCreateTime\s*=\s*\'(\d+)\'', html_content)
        if match_time:
            formatted_time = format_pub_time(match_time.group(1))
            if formatted_time:
                pub_time_div.string = formatted_time

    # 5. Render IP location
    ip_wrp = soup.find(id="js_ip_wording_wrp")
    ip_wording = soup.find(id="js_ip_wording")
    if ip_wrp and ip_wording:
        # Regex search for window.ip_wording block
        ip_match = re.search(r'window\.ip_wording\s*=\s*({[^}]+})', html_content, re.DOTALL)
        if ip_match:
            ip_block = ip_match.group(1)
            # Extract simple fields
            country_id_m = re.search(r'countryId:\s*\'?(\d+)\'?', ip_block)
            country_name_m = re.search(r'countryName:\s*\'([^\'\s]+)\'', ip_block)
            province_name_m = re.search(r'provinceName:\s*\'([^\'\s]+)\'', ip_block)
            
            ip_display = ""
            if country_id_m and int(country_id_m.group(1)) == 156:
                if province_name_m:
                    ip_display = province_name_m.group(1)
            elif country_name_m:
                ip_display = country_name_m.group(1)
                
            if ip_display:
                ip_wording.string = ip_display
                # Ensure displayed
                if ip_wrp.has_attr("style"):
                    ip_wrp["style"] = "display: inline-block;"
                else:
                    ip_wrp["style"] = "display: inline-block;"
            else:
                ip_wrp.decompose()
        else:
            ip_wrp.decompose()

    # 6. Render Title Modified info
    title_modify_wrp = soup.find(id="js_title_modify_wrp")
    title_modify = soup.find(id="js_title_modify")
    if title_modify_wrp:
        is_modified_match = re.search(r'window\.isTitleModified\s*=\s*"(\d*)"\s*\* \s*1;', html_content)
        if is_modified_match and is_modified_match.group(1) == "1":
            if title_modify:
                title_modify.string = "标题已修改"
            title_modify_wrp["style"] = "display: inline-block;"
        else:
            title_modify_wrp.decompose()

    # 7. Article Share Source (Repost link)
    share_source = soup.find(id="js_share_source")
    if share_source and share_source.has_attr("data-url"):
        source_url = share_source["data-url"]
        # Convert span to a tag
        link_tag = soup.new_tag("a", href=source_url, attrs={"class": share_source.get("class", [])})
        link_tag.extend(share_source.contents)
        share_source.replace_with(link_tag)

    # 8. Text message share page
    text_desc = soup.find(id="js_text_desc")
    if text_desc:
        body_cls = soup.body.get("class", []) if soup.body else []
        if "page_share_text" not in body_cls:
            if isinstance(body_cls, list):
                body_cls.append("page_share_text")
            else:
                body_cls = f"{body_cls} page_share_text".strip()
            if soup.body:
                soup.body["class"] = body_cls

        desc_text = text_desc.get_text().strip()
        if not desc_text:
            # Attempt to extract from QMTPL
            qmtpl = extract_js_object(html_content, "window.__QMTPL_SSR_DATA__")
            if qmtpl and "title" in qmtpl:
                desc_text = qmtpl["title"].replace('\r', '').replace('\n', '<br>')
            
            if not desc_text:
                # Fallback to TextContentNoEncode
                text_match = re.search(r'var\s+TextContentNoEncode\s*=\s*window\.a_value_which_never_exists\s*\|\|\s*\'([^\']*)\'', html_content)
                if text_match:
                    desc_text = text_match.group(1).replace('\r', '').replace('\n', '<br>')
                else:
                    content_match = re.search(r'var\s+ContentNoEncode\s*=\s*window\.a_value_which_never_exists\s*\|\|\s*\'([^\']*)\'', html_content)
                    if content_match:
                        desc_text = content_match.group(1).replace('\r', '').replace('\n', '<br>')

            if desc_text:
                text_desc.append(BeautifulSoup(desc_text, 'html.parser'))
        
        top_profile = soup.find(id="js_top_profile")
        if top_profile and top_profile.has_attr("class"):
            classes = top_profile["class"]
            if "profile_area_hide" in classes:
                classes.remove("profile_area_hide")
                top_profile["class"] = classes

    # 9. Image message share page
    image_desc = soup.find(id="js_image_desc")
    if image_desc:
        body_cls = soup.body.get("class", []) if soup.body else []
        if "page_share_img" not in body_cls:
            if isinstance(body_cls, list):
                body_cls.append("pages_skin_pc")
                body_cls.append("page_share_img")
            else:
                body_cls = f"{body_cls} pages_skin_pc page_share_img".strip()
            if soup.body:
                soup.body["class"] = body_cls

        desc_text = image_desc.get_text().strip()
        if not desc_text:
            qmtpl = extract_js_object(html_content, "window.__QMTPL_SSR_DATA__")
            if qmtpl and "desc" in qmtpl:
                desc_text = qmtpl["desc"].replace('\r', '').replace('\n', '<br>').replace(' ', '&nbsp;')
            if desc_text:
                image_desc.append(BeautifulSoup(desc_text, 'html.parser'))

        # Append images in list
        container_el = soup.find(id="js_share_content_page_hd")
        if container_el:
            # Extract list from JS
            match = re.search(r'window\.picture_page_info_list\s*=\s*(.+?\.slice\(0,\s*20\);|\[.+?\])', html_content, re.DOTALL)
            if match:
                block = match.group(1)
                cdn_urls = re.findall(r'cdn_url:\s*\'([^\'\s]+)\'', block)
                
                img_div_html = '<div style="display: flex; flex-direction: column; align-items: center; gap: 10px; padding-block: 20px;">'
                for url in cdn_urls:
                    clean_url = url.replace('\\/', '/')
                    img_div_html += f'<img src="{clean_url}" alt="" style="display: block; border: 1px solid gray; border-radius: 5px; max-width: 90%; cursor: pointer;" onclick="window.open(this.src)" />'
                img_div_html += '</div>'
                container_el.append(BeautifulSoup(img_div_html, 'html.parser'))

        top_profile = soup.find(id="js_top_profile")
        if top_profile and top_profile.has_attr("class"):
            classes = top_profile["class"]
            if "profile_area_hide" in classes:
                classes.remove("profile_area_hide")
                top_profile["class"] = classes

    # 10. Extract stylesheets link elements and rebuild head
    stylesheets_html = ""
    for link in soup.find_all("link"):
        rel = link.get("rel", [])
        is_stylesheet = False
        if isinstance(rel, list):
            is_stylesheet = "stylesheet" in [r.lower() for r in rel]
        elif isinstance(rel, str):
            is_stylesheet = rel.lower() == "stylesheet"

        if is_stylesheet:
            href = link.get("href")
            if href:
                if href.startswith("//"):
                    href = "https:" + href
                stylesheets_html += f'<link rel="stylesheet" href="{href}">\n'
            link.decompose()

    # Extract article layout nodes
    article_node = soup.find(id="js_article")
    article_html = str(article_node) if article_node else ""
    
    bottom_bar_node = soup.find(id="js_article_bottom_bar")
    bottom_bar_html = str(bottom_bar_node) if bottom_bar_node else ""

    body_class_str = " ".join(soup.body.get("class", [])) if (soup.body and soup.body.get("class")) else ""

    # Reconstruct clean structured HTML page
    normalized_html = f"""<!DOCTYPE html>
<html lang="zh_CN">
<head>
    <meta charset="utf-8">
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0,user-scalable=0,viewport-fit=cover">
    <meta name="referrer" content="no-referrer">
    <title>{metadata.get('title', 'Untitled Article')}</title>
    {stylesheets_html}
    <style>
        #page-content,
        #js_article_bottom_bar,
        .__page_content__ {{
            max-width: 667px;
            margin: 0 auto;
        }}
        img {{
            max-width: 100%;
        }}
        .sns_opr_btn::before {{
            width: 16px;
            height: 16px;
            margin-right: 3px;
        }}
    </style>
</head>
<body class="{body_class_str}">
{article_html}
{bottom_bar_html}
</body>
</html>"""

    return normalized_html


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Clean and normalize raw WeChat HTML, bypassing hotlinking constraints.")
    parser.add_argument("--in", dest="in_dir", required=True, help="Input directory containing raw HTML files (html_raw/).")
    parser.add_argument("--out", dest="out_dir", required=True, help="Output directory where normalized HTML files will be saved.")
    parser.add_argument("--meta", dest="meta_dir", help="Metadata directory containing json files (optional, default to sibling of html_raw/).")
    args = parser.parse_args()

    if not os.path.exists(args.in_dir):
        logger.error(f"Input directory does not exist: {args.in_dir}")
        sys.exit(1)

    os.makedirs(args.out_dir, exist_ok=True)

    # Resolve meta directory
    meta_dir = args.meta_dir
    if not meta_dir:
        parent = os.path.dirname(os.path.abspath(args.in_dir.rstrip('/')))
        meta_dir = os.path.join(parent, "meta")

    # List all raw HTML files
    html_files = [f for f in os.listdir(args.in_dir) if f.endswith('.html')]
    if not html_files:
        logger.info(f"No HTML files found in {args.in_dir}")
        sys.exit(0)

    logger.info(f"Found {len(html_files)} HTML files to normalize.")

    success_count = 0
    for hf in html_files:
        stem = os.path.splitext(hf)[0]
        html_path = os.path.join(args.in_dir, hf)
        meta_path = os.path.join(meta_dir, f"{stem}.json") if os.path.exists(meta_dir) else None
        
        out_html_path = os.path.join(args.out_dir, f"{stem}.html")
        
        try:
            normalized_content = clean_and_normalize_html(html_path, meta_path)
            with open(out_html_path, 'w', encoding='utf-8') as f:
                f.write(normalized_content)
            success_count += 1
            logger.info(f"Normalized: {hf} -> {stem}.html")
        except Exception as e:
            logger.error(f"Failed to normalize {hf}. Error: {e}")

    logger.info(f"Normalization complete. Successfully cleaned {success_count}/{len(html_files)} files.")


if __name__ == "__main__":
    main()

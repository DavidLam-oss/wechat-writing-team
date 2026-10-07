#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
WeChat Official Account Article Downloader
Uses a pool of Cloudflare Workers to proxy requests and bypass hotlinking/anti-scraping checks.
"""

import os
import sys
import re
import json
import time
import urllib.request
import urllib.parse
import ssl
import logging
import concurrent.futures
from dataclasses import dataclass, asdict
from typing import List, Dict, Tuple, Optional

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("downloader")

ALLOWED_HOSTS = {'mp.weixin.qq.com', 'api.weixin.qq.com'}

# Optional: hostnames of your own dedicated proxies, which get priority over the
# shared/public pool. Provide a comma-separated list via the environment variable
# DWT_PRIVATE_PROXY_HOSTS (substring match), e.g. "proxy-a.example.com,proxy-b.example.com".
# Leave empty to rely solely on the public pool in proxy_pool.txt.
PRIVATE_PROXY_HOSTS = [h.strip() for h in os.environ.get("DWT_PRIVATE_PROXY_HOSTS", "").split(",") if h.strip()]


def _is_private_proxy(proxy: str) -> bool:
    """Return True if `proxy` matches one of the user-configured dedicated hosts."""
    return any(host in proxy for host in PRIVATE_PROXY_HOSTS)


@dataclass
class ProxyStatus:
    failures: int = 0
    last_used: float = 0.0
    cooldown: bool = False
    total_failures: int = 0
    total_success: int = 0
    total_use: int = 0

class ProxyManager:
    def __init__(self, pool_file: str = None, cooldown_period: float = 60.0, max_failures: int = 3):
        self.cooldown_period = cooldown_period
        self.max_failures = max_failures
        self.proxies: List[str] = []
        self.proxy_status: Dict[str, ProxyStatus] = {}

        if pool_file is None:
            pool_file = os.path.join(os.path.dirname(__file__), 'proxy_pool.txt')

        self._load_proxies(pool_file)

    def _load_proxies(self, pool_file: str):
        if not os.path.exists(pool_file):
            logger.warning(f"Proxy pool file not found at {pool_file}. Running without proxies.")
            return

        with open(pool_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    self.proxies.append(line)
                    self.proxy_status[line] = ProxyStatus()

        if self.proxies:
            logger.info(f"Loaded {len(self.proxies)} proxy workers from {pool_file}")
        else:
            logger.warning("Proxy pool is empty.")

    def get_best_proxy(self) -> Optional[str]:
        if not self.proxies:
            return None

        now = time.time()
        
        # Classify available proxies (either not in cooldown, or cooldown has expired)
        available_private = []
        available_public = []
        
        for p in self.proxies:
            status = self.proxy_status[p]
            is_available = not status.cooldown or (now - status.last_used >= self.cooldown_period)
            
            if is_available:
                if _is_private_proxy(p):
                    available_private.append((p, status))
                else:
                    available_public.append((p, status))

        # 1. Prefer user-configured dedicated proxies (see DWT_PRIVATE_PROXY_HOSTS)
        if available_private:
            available_private.sort(key=lambda x: (x[1].failures, x[1].last_used))
            best_proxy, status = available_private[0]
            status.last_used = now
            status.total_use += 1
            return best_proxy

        # 2. Fallback to public proxies
        if available_public:
            available_public.sort(key=lambda x: (x[1].failures, x[1].last_used))
            best_proxy, status = available_public[0]
            status.last_used = now
            status.total_use += 1
            return best_proxy

        # 3. Fallback: Reset and get proxy
        return self._reset_and_get_proxy()

    def _reset_and_get_proxy(self) -> str:
        # Prioritize resetting user-configured dedicated proxies first
        private_proxies = [p for p in self.proxies if _is_private_proxy(p)]
        candidates = private_proxies if private_proxies else self.proxies
        
        # Find the candidate used longest ago
        oldest_proxy = min(candidates, key=lambda p: self.proxy_status[p].last_used)
        status = self.proxy_status[oldest_proxy]
        
        status.failures = 0
        status.cooldown = False
        status.last_used = time.time()
        status.total_use += 1
        logger.info(f"All proxies in cooldown. Resetting oldest proxy: {oldest_proxy}")
        return oldest_proxy

    def record_success(self, proxy: str):
        if proxy in self.proxy_status:
            status = self.proxy_status[proxy]
            status.failures = 0
            status.cooldown = False
            status.total_success += 1

    def record_failure(self, proxy: str):
        if proxy in self.proxy_status:
            status = self.proxy_status[proxy]
            status.failures += 1
            status.total_failures += 1
            if status.failures >= self.max_failures:
                status.cooldown = True
                logger.warning(f"Proxy {proxy} reached max failures ({status.failures}). Cooling down.")


class Downloader:
    def __init__(self, proxy_manager: ProxyManager = None, timeout: float = 30.0):
        # None means "no proxy pool" -> direct connection, which is the default.
        # The CF Worker pool is opt-in via the CLI flag --proxy.
        self.proxy_manager = proxy_manager
        self.timeout = timeout
        try:
            self.ssl_context = ssl._create_unverified_context()
        except AttributeError:
            self.ssl_context = None

    def is_valid_url(self, url: str) -> bool:
        try:
            parsed = urllib.parse.urlparse(url)
            # Support both netloc and check host
            host = parsed.netloc.split(':')[0]
            return parsed.scheme == 'https' and host in ALLOWED_HOSTS
        except Exception:
            return False

    def _download_direct(self, url: str, headers: Dict[str, str]) -> Tuple[bytes, Optional[str]]:
        """Issue a direct HTTPS request to the target host (no proxy involved)."""
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=self.timeout, context=self.ssl_context) as response:
            return response.read(), None

    def download(self, url: str, headers: Dict[str, str] = None) -> Tuple[bytes, Optional[str]]:
        """
        Downloads a WeChat article, directly or through a proxy worker.
        Returns: Tuple of (html_bytes, proxy_used)
        """
        if not self.is_valid_url(url):
            raise ValueError(f"Invalid target URL: {url}. Must be https://mp.weixin.qq.com or https://api.weixin.qq.com")

        headers = headers or {}
        if 'User-Agent' not in headers:
            headers['User-Agent'] = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

        proxy = self.proxy_manager.get_best_proxy() if self.proxy_manager else None
        
        if not proxy:
            # Direct connection: no proxy pool requested, or the pool is empty / its file is missing.
            logger.info("No proxy available. Downloading directly.")
            return self._download_direct(url, headers)

        # Build proxy URL
        params = {
            'url': url,
            'headers': json.dumps(headers),
            'preset': 'mp'
        }
        proxy_url = f"{proxy}?{urllib.parse.urlencode(params)}"
        
        # Exponential backoff retry logic (3 times: 1s, 2s, 4s delay)
        last_error = None
        for attempt in range(3):
            try:
                req = urllib.request.Request(proxy_url)
                with urllib.request.urlopen(req, timeout=self.timeout, context=self.ssl_context) as response:
                    if response.status != 200:
                        raise urllib.error.HTTPError(
                            response.url, response.status, f"HTTP Error {response.status}", response.headers, None
                        )
                    html_bytes = response.read()
                    self.proxy_manager.record_success(proxy)
                    return html_bytes, proxy
            except Exception as e:
                last_error = e
                self.proxy_manager.record_failure(proxy)
                delay = 2 ** attempt  # 1s, 2s, 4s
                logger.warning(f"Failed download attempt {attempt+1}/3 using proxy {proxy}. Error: {e}. Retrying in {delay}s...")
                time.sleep(delay)
                # Rotate proxy for next retry attempt
                proxy = self.proxy_manager.get_best_proxy()
                if proxy:
                    params['url'] = url
                    proxy_url = f"{proxy}?{urllib.parse.urlencode(params)}"

        # Every proxy attempt failed. Degrade gracefully instead of aborting the batch:
        # try one direct request before giving up on this URL.
        logger.warning(f"All proxy attempts failed (last error: {last_error}). Falling back to a direct download.")
        try:
            return self._download_direct(url, headers)
        except Exception as direct_error:
            raise RuntimeError(
                f"Failed after 3 proxy attempts and a direct fallback. "
                f"Proxy error: {last_error}. Direct error: {direct_error}"
            ) from direct_error


def sanitize_filename(name: str) -> str:
    # Remove illegal characters for Windows/macOS file systems
    sanitized = re.sub(r'[\\/*?:"<>|\n\r\t]', '', name)
    sanitized = sanitized.strip()
    return sanitized if sanitized else "untitled_article"


def extract_metadata(html: str, url: str) -> Dict[str, str]:
    """
    Extract title, author, and publish time from WeChat raw HTML via regex (no extra deps).
    """
    meta = {
        "title": "Untitled Article",
        "author": "Unknown Author",
        "publish_time": "",
        "source_url": url,
        "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    # Extract Title
    title_match = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', html)
    if title_match:
        meta["title"] = urllib.parse.unquote(title_match.group(1))
    else:
        title_tag = re.search(r'<h1[^>]*class="[^"]*rich_media_title[^"]*"[^>]*id="activity-name"[^>]*>\s*([^\s<][^<]*[^\s<])', html, re.DOTALL)
        if title_tag:
            meta["title"] = title_tag.group(1).strip()

    # Clean HTML entities in title
    meta["title"] = meta["title"].replace("&quot;", '"').replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&#39;", "'")

    # Extract Author / Nickname
    author_match = re.search(r'<meta\s+property="og:article:author"\s+content="([^"]+)"', html)
    if author_match:
        meta["author"] = author_match.group(1).strip()
    else:
        nickname_match = re.search(r'var\s+nickname\s*=\s*"([^"]+)"', html)
        if nickname_match:
            meta["author"] = nickname_match.group(1).strip()

    # Extract Publish Time (oriCreateTime unix timestamp)
    time_match = re.search(r'var\s+oriCreateTime\s*=\s*\'(\d+)\'', html)
    if time_match:
        unix_time = int(time_match.group(1))
        meta["publish_time"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(unix_time))
    
    return meta


def process_single_link(downloader: Downloader, url: str, out_dir: str, headers: Dict[str, str] = None, delay: float = 0.0) -> Dict:
    start_time = time.time()
    url = url.strip()
    
    # Generate backup ID based on timestamp and url hash if extraction fails
    url_hash = str(abs(hash(url)))[:8]
    backup_id = f"wechat_{url_hash}_{int(start_time)}"
    
    result = {
        "url": url,
        "status": "failed",
        "error": None,
        "title": None,
        "filename": None,
        "proxy": None,
        "elapsed": 0.0
    }

    try:
        if delay > 0:
            import random
            sleep_time = random.uniform(delay * 0.5, delay * 1.5)
            time.sleep(sleep_time)
            
        html_bytes, proxy_used = downloader.download(url, headers)
        result["proxy"] = proxy_used
        html_str = html_bytes.decode('utf-8', errors='ignore')
        
        # Parse metadata
        meta = extract_metadata(html_str, url)
        meta["proxy_used"] = proxy_used or "direct"
        
        # Determine filename
        filename_stem = sanitize_filename(meta["title"])
        if filename_stem == "Untitled Article":
            # Check for biz/mid in URL as fallback stem name
            match_biz = re.search(r'__biz=([^&]+)', url)
            match_mid = re.search(r'mid=([^&]+)', url)
            if match_biz and match_mid:
                filename_stem = f"{match_biz.group(1)[:8]}_{match_mid.group(1)}"
            else:
                filename_stem = backup_id
                
        # Handle filename collisions cleanly
        out_html_path = os.path.join(out_dir, "html_raw", f"{filename_stem}.html")
        counter = 1
        base_stem = filename_stem
        while os.path.exists(out_html_path):
            filename_stem = f"{base_stem}_{counter}"
            out_html_path = os.path.join(out_dir, "html_raw", f"{filename_stem}.html")
            counter += 1

        # Save HTML Raw
        with open(out_html_path, 'wb') as f:
            f.write(html_bytes)
            
        # Save Metadata
        out_meta_path = os.path.join(out_dir, "meta", f"{filename_stem}.json")
        with open(out_meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        result["status"] = "success"
        result["title"] = meta["title"]
        result["filename"] = filename_stem
        logger.info(f"Successfully downloaded: {meta['title']} -> {filename_stem}.html")

    except Exception as e:
        result["error"] = str(e)
        logger.error(f"Failed to process {url}. Error: {e}")

    result["elapsed"] = round(time.time() - start_time, 2)
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Batch downloader for WeChat Official Account articles using Cloudflare Worker proxies.")
    parser.add_argument("--links", required=True, help="Path to text file containing target WeChat article URLs (one per line).")
    parser.add_argument("--out", required=True, help="Output root directory where html_raw/ and meta/ will be saved.")
    parser.add_argument("--concurrency", type=int, default=5, help="Number of threads for concurrent downloading (default: 5).")
    parser.add_argument("--cookie", help="WeChat official backend account Cookie for authenticated requests (bypasses GFW/CAPTCHA wind control).")
    parser.add_argument("--delay", type=float, default=0.0, help="Average random delay in seconds between requests to prevent rate limit blocks.")
    parser.add_argument("--proxy", action="store_true", help="Enable Cloudflare Worker proxy pool (requires proxy_pool.txt and VPN). Default: False.")
    args = parser.parse_args()

    if not os.path.exists(args.links):
        logger.error(f"Links file not found: {args.links}")
        sys.exit(1)

    # Read and deduplicate links
    urls = []
    with open(args.links, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                urls.append(line)
    
    # Remove duplicates preserving order
    unique_urls = list(dict.fromkeys(urls))
    logger.info(f"Found {len(unique_urls)} unique URLs out of {len(urls)} total lines in {args.links}")

    if not unique_urls:
        logger.error("No valid links to download.")
        sys.exit(0)

    # Ensure output directories exist
    os.makedirs(os.path.join(args.out, "html_raw"), exist_ok=True)
    os.makedirs(os.path.join(args.out, "meta"), exist_ok=True)

    # Save links pool manifest
    links_manifest = {
        "urls": unique_urls,
        "source_route": "link-pool",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    with open(os.path.join(args.out, "links.json"), 'w', encoding='utf-8') as f:
        json.dump(links_manifest, f, ensure_ascii=False, indent=2)

    # Build request headers
    headers = {}
    if args.cookie:
        headers["Cookie"] = args.cookie

    # Init Downloader (Disabled proxy pool by default)
    pm = ProxyManager() if args.proxy else None
    downloader = Downloader(proxy_manager=pm)

    # Multi-threaded download execution
    start_time = time.time()
    per_url_results = []
    
    logger.info(f"Starting batch download with concurrency={args.concurrency}...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        future_to_url = {executor.submit(process_single_link, downloader, url, args.out, headers, args.delay): url for url in unique_urls}
        for future in concurrent.futures.as_completed(future_to_url):
            res = future.result()
            per_url_results.append(res)

    elapsed = round(time.time() - start_time, 2)
    success_count = sum(1 for r in per_url_results if r["status"] == "success")
    failed_count = len(unique_urls) - success_count

    # Generate download report
    report = {
        "success": success_count,
        "failed": failed_count,
        "elapsed_sec": elapsed,
        "per_url": per_url_results
    }
    with open(os.path.join(args.out, "download-report.json"), 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info(f"Batch completed in {elapsed}s. Success: {success_count}, Failed: {failed_count}.")
    logger.info(f"Report saved to {os.path.join(args.out, 'download-report.json')}")

if __name__ == "__main__":
    main()

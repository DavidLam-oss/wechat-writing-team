#!/usr/bin/env python3
"""WeChat Director —— GPT-Image-2 生图适配器。"""
import base64
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

try:
    import requests
    from requests import HTTPError as RequestsHTTPError
    REQUESTS_AVAILABLE = True
except ImportError:
    requests = None
    RequestsHTTPError = ()
    REQUESTS_AVAILABLE = False

from director_core import ASSETS_DIR, logger, require_config

def _extract_gpt_image2_result(data):
    """Return ("url"|"b64"|"task", value) from common image response shapes."""
    candidates = []
    if isinstance(data, dict):
        if isinstance(data.get("data"), list):
            candidates.extend(data["data"])
        elif isinstance(data.get("data"), dict):
            candidates.append(data["data"])
        candidates.append(data)

    for item in candidates:
        if not isinstance(item, dict):
            continue

        for key in ("url", "image_url", "image"):
            value = item.get(key)
            if isinstance(value, list) and value:
                return "url", value[0]
            if isinstance(value, str) and value:
                return "url", value

        if item.get("b64_json"):
            return "b64", item["b64_json"]
        if item.get("task_id"):
            return "task", item["task_id"]

        result = item.get("result")
        if isinstance(result, dict):
            images = result.get("images")
            if isinstance(images, list) and images:
                first_image = images[0]
                if isinstance(first_image, dict):
                    image_url = first_image.get("url")
                    if isinstance(image_url, list) and image_url:
                        return "url", image_url[0]
                    if isinstance(image_url, str) and image_url:
                        return "url", image_url

    raise RuntimeError(f"No image result in response: {str(data)[:300]}")


def _download_image_bytes(image_url):
    if REQUESTS_AVAILABLE:
        response = requests.get(image_url, timeout=120, proxies={"http": None, "https": None})
        response.raise_for_status()
        return response.content

    with urllib.request.urlopen(image_url, timeout=120) as resp:
        return resp.read()


def _poll_gpt_image2_task(api_config, task_id):
    task_url = f"{api_config['base_url'].rstrip('/')}/tasks/{task_id}"
    headers = {
        "Authorization": f"Bearer {api_config['api_key']}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (compatible; WeChatConverter/2.7)"
    }
    for _ in range(80):
        time.sleep(3)
        if REQUESTS_AVAILABLE:
            response = requests.get(task_url, headers=headers, timeout=30, proxies={"http": None, "https": None})
            response.raise_for_status()
            result_data = response.json()
        else:
            poll_req = urllib.request.Request(task_url, headers=headers)
            with urllib.request.urlopen(poll_req, timeout=30) as resp:
                result_data = json.load(resp)

        status_data = result_data.get("data", result_data)
        if not isinstance(status_data, dict):
            continue

        task_status = status_data.get("status")
        if task_status in ("completed", "succeeded", "success"):
            result_type, value = _extract_gpt_image2_result(result_data)
            if result_type == "url":
                return _download_image_bytes(value)
            if result_type == "b64":
                return base64.b64decode(value)
        if task_status in ("failed", "error", "cancelled"):
            raise RuntimeError(f"GPT-Image2 task failed: {str(result_data)[:300]}")

    raise RuntimeError("GPT-Image2 task timed out after polling")


def submit_task_gpt_image2(api_config, prompt, width, height, use_ip=False):
    """Generate image via gpt-image-2 using apimart's image endpoint."""
    require_config(api_config, "GPT-Image2", ["base_url", "model", "api_key"])

    # Convert dimensions to aspect ratio string
    # Supported: 1:1, 3:2, 2:3, 4:3, 3:4, 5:4, 4:5, 16:9, 9:16, 2:1, 1:2, 21:9, 9:21
    ratio = width / height
    if abs(ratio - 2.35) < 0.05:
        size_str = "16:9"
    elif abs(ratio - 1.0) < 0.05:
        size_str = "1:1"
    elif abs(ratio - 0.75) < 0.05:
        size_str = "3:4"
    elif abs(ratio - 1.33) < 0.05:
        size_str = "4:3"
    elif abs(ratio - 0.667) < 0.05:
        size_str = "2:3"
    elif abs(ratio - 1.5) < 0.05:
        size_str = "3:2"
    elif abs(ratio - 1.78) < 0.05:
        size_str = "16:9"
    elif abs(ratio - 0.5625) < 0.05:
        size_str = "9:16"
    elif abs(ratio - 2.0) < 0.05:
        size_str = "2:1"
    elif abs(ratio - 0.5) < 0.05:
        size_str = "1:2"
    elif abs(ratio - 2.43) < 0.05:
        size_str = "21:9"
    elif abs(ratio - 0.412) < 0.05:
        size_str = "9:21"
    else:
        size_str = "1:1"  # fallback

    url = f"{api_config['base_url'].rstrip('/')}/images/generations"
    headers = {
        "Authorization": f"Bearer {api_config['api_key']}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (compatible; WeChatConverter/2.7)",
        "Connection": "close"
    }
    payload = {
        "model": api_config["model"],
        "prompt": prompt,
        "size": size_str,
        "n": 1,
        "resolution": api_config.get("resolution", "1k")
    }

    # IP Injection
    if use_ip:
        ip_image_path = ASSETS_DIR / "IP_Reference.png"
        if ip_image_path.exists():
            try:
                with open(ip_image_path, "rb") as img_f:
                    b64_img = base64.b64encode(img_f.read()).decode("utf-8")
                    payload["image_urls"] = [f"data:image/png;base64,{b64_img}"]
                logger.info("[GPT-Image2] IP Reference injected")
            except Exception as e:
                logger.warning(f"[GPT-Image2] Failed to load IP image: {e}")
        else:
            logger.warning("[GPT-Image2] IP flag is ON, but reference image not found.")

    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            if REQUESTS_AVAILABLE:
                response = requests.post(url, json=payload, headers=headers, timeout=300, proxies={"http": None, "https": None})
                response.raise_for_status()
                data = response.json()
            else:
                req = urllib.request.Request(url, headers=headers, data=json.dumps(payload).encode('utf-8'))
                with urllib.request.urlopen(req, timeout=300) as resp:
                    data = json.load(resp)

            result_type, value = _extract_gpt_image2_result(data)
            if result_type == "url":
                return _download_image_bytes(value)
            if result_type == "b64":
                return base64.b64decode(value)
            if result_type == "task":
                return _poll_gpt_image2_task(api_config, value)
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', errors='replace')
            if (e.code == 429 or 500 <= e.code < 600) and attempt < max_retries:
                logger.info(f"[GPT-Image2] Error {e.code}, retrying in 5s...")
                time.sleep(5)
                continue
            raise RuntimeError(f"GPT-Image2 failed ({e.code}): {body[:200]}...") from e
        except RequestsHTTPError as e:
            status = e.response.status_code if e.response is not None else "unknown"
            body = e.response.text if e.response is not None else str(e)
            if (status == 429 or (isinstance(status, int) and 500 <= status < 600)) and attempt < max_retries:
                logger.info(f"[GPT-Image2] Error {status}, retrying in 5s...")
                time.sleep(5)
                continue
            raise RuntimeError(f"GPT-Image2 failed ({status}): {body[:200]}...") from e
        except Exception as e:
            if attempt < max_retries:
                logger.info(f"[GPT-Image2] Network error ({e}), retrying in 5s...")
                time.sleep(5)
                continue
            raise RuntimeError(f"GPT-Image2 network failed: {e}") from e
    raise RuntimeError("GPT-Image2 failed without a usable response")

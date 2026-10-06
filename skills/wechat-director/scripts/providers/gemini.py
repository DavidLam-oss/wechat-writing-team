#!/usr/bin/env python3
"""WeChat Director —— Gemini 生图适配器（API 与 Web 两条通道）。"""
import base64
import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from director_core import ASSETS_DIR, get_skill_root, logger, require_config

def resolve_gemini_web_settings(api_config):
    """解析 gemini-web 的 vendor 路径与运行时目录。

    - **vendor 脚本**：位于技能自身目录下（`<skill>/vendor/...`）。技能被复制
      到任意位置、任意宿主都能找到，不使用仓库名或机器绝对路径。
    - **运行时**（cookie / chrome profile）：默认放在用户主目录下，避免写入
      可能只读或被同步的技能目录；可用 api_keys.json 的 `gemini_web.runtime_dir` 覆盖。
    """
    skill_root = get_skill_root()
    provider_config = api_config.get("gemini_web", {})
    runtime_dir = Path(provider_config.get(
        "runtime_dir",
        Path.home() / ".gemini" / "wechat-director" / "gemini-web"
    ))

    return {
        "model": provider_config.get("model", "gemini-3-pro"),
        "timeout": int(provider_config.get("timeout", 240)),
        "script_dir": (
            skill_root / "vendor" / "baoyu-danger-gemini-web" / "scripts"
        ),
        "data_dir": Path(provider_config.get("data_dir", runtime_dir / "data")),
        "cookie_path": Path(provider_config.get("cookie_path", runtime_dir / "cookies.json")),
        "profile_dir": Path(provider_config.get("profile_dir", runtime_dir / "chrome-profile")),
    }


def run_gemini_web_command(api_config, extra_args, timeout=None):
    settings = resolve_gemini_web_settings(api_config)
    script_dir = settings["script_dir"]
    bun_path = shutil.which("bun")

    if not script_dir.exists():
        raise FileNotFoundError(f"Gemini Web backend not found: {script_dir}")
    if not bun_path:
        raise RuntimeError("bun is required for gemini-web provider, but was not found in PATH.")

    settings["data_dir"].mkdir(parents=True, exist_ok=True)
    settings["profile_dir"].mkdir(parents=True, exist_ok=True)
    settings["cookie_path"].parent.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["GEMINI_WEB_DATA_DIR"] = str(settings["data_dir"])
    env["GEMINI_WEB_CHROME_PROFILE_DIR"] = str(settings["profile_dir"])
    env["GEMINI_WEB_COOKIE_PATH"] = str(settings["cookie_path"])

    cmd = [bun_path, "run", "main.ts", *extra_args]
    result = subprocess.run(
        cmd,
        cwd=script_dir,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout or settings["timeout"],
    )

    if result.returncode != 0:
        stderr = (result.stderr or result.stdout or "").strip()
        login_hint = ""
        lower_err = stderr.lower()
        if "login" in lower_err or "auth" in lower_err or "cookie" in lower_err:
            login_hint = " Run visualize.py with --gemini-web-login once first."
        raise RuntimeError(f"gemini-web failed: {stderr[:400]}{login_hint}")

    return result, settings


# --- Generation Logic ---

def submit_task_gemini(api_config, prompt, width, height, use_ip=False, ratio_suffix=""):
    require_config(api_config, "Gemini API", ["base_url", "model", "api_key"])

    # Normalize base_url
    base_url = api_config['base_url'].rstrip('/')
    if base_url.endswith('/models'): base_url = base_url[:-7]

    # Dynamic Model Selection
    base_model = api_config['model']
    model_id = f"{base_model}{ratio_suffix}"

    url = f"{base_url}/models/{model_id}:generateContent"
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_config['api_key']}

    parts = [{"text": prompt}]
    w, h = int(width), int(height)
    ratio = w / h

    # Prompt Tuning for Aspect Ratio (even if model handles it, this helps composition)
    if ratio > 1.7:
        parts[0]["text"] += ", cinematic anamorphic shot, 2.35:1 aspect ratio"
    elif ratio < 0.6:
        parts[0]["text"] += ", tall portrait shot, 9:16 aspect ratio"
    elif ratio < 0.85:
        parts[0]["text"] += ", portrait shot, 3:4 aspect ratio"

    # IP Injection
    if use_ip:
        ip_image_path = ASSETS_DIR / "IP_Reference.png"
        if ip_image_path.exists():
            try:
                with open(ip_image_path, "rb") as img_f:
                    b64_img = base64.b64encode(img_f.read()).decode("utf-8")
                    parts.append({"inlineData": {"mimeType": "image/png", "data": b64_img}})
                logger.info("[Gemini] IP Reference injected")
            except Exception as e:
                logger.warning(f"[Gemini] Failed to load IP image: {e}")
        else:
            logger.warning("[Gemini] IP flag is ON, but reference image not found.")

    payload = {
        "contents": [{"role": "user", "parts": parts}]
    }

    req = urllib.request.Request(url, headers=headers, data=json.dumps(payload).encode('utf-8'))

    max_retries = 1
    for attempt in range(max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = json.load(resp)
                try:
                    candidate = data["candidates"][0]
                    parts_resp = candidate["content"]["parts"]
                    image_data = None
                    for part in parts_resp:
                        if "inlineData" in part: image_data = part["inlineData"]["data"]; break
                        if "inline_data" in part: image_data = part["inline_data"]["data"]; break

                    if image_data: return image_data
                    raise RuntimeError(f"No image data. Preview: {str(parts_resp)[:200]}")
                except (KeyError, IndexError) as e:
                    raise RuntimeError(f"Unexpected format: {str(data)[:500]}") from e
        except urllib.error.HTTPError as e:
            # Fallback for 404 (Model suffix not found)
            if e.code == 404:
                logger.warning(f"⚠️ Model {model_id} not found (404). Falling back to base {base_model}...")
                if ratio_suffix != "":
                     # Recursive call without suffix
                     return submit_task_gemini(api_config, prompt, width, height, use_ip, ratio_suffix="")

            if (e.code == 429 or 500 <= e.code < 600) and attempt < max_retries:
                logger.info(f"[Gemini] Error {e.code}, retrying...")
                time.sleep(2)
                continue
            raise RuntimeError(f"Gemini failed ({e.code}): {e.read().decode('utf-8', errors='replace')[:200]}...") from e


def submit_task_gemini_web(api_config, prompt, output_path, use_ip=False):
    settings = resolve_gemini_web_settings(api_config)
    cmd = [
        "--prompt", prompt,
        "--image", str(output_path),
        "--model", settings["model"],
        "--profile-dir", str(settings["profile_dir"]),
        "--cookie-path", str(settings["cookie_path"]),
    ]

    if use_ip:
        ip_image_path = ASSETS_DIR / "IP_Reference.png"
        if ip_image_path.exists():
            cmd.extend(["--reference", str(ip_image_path)])
            logger.info("[Gemini Web] IP Reference injected")
        else:
            logger.warning("[Gemini Web] IP flag is ON, but reference image not found.")

    run_gemini_web_command(api_config, cmd, timeout=settings["timeout"])

    if not output_path.exists():
        raise RuntimeError(f"gemini-web did not create output file: {output_path}")


def login_gemini_web(api_config):
    result, settings = run_gemini_web_command(
        api_config,
        [
            "--login",
            "--profile-dir", str(resolve_gemini_web_settings(api_config)["profile_dir"]),
            "--cookie-path", str(resolve_gemini_web_settings(api_config)["cookie_path"]),
        ],
        timeout=300,
    )
    logger.info(result.stdout.strip() or f"Gemini Web login prepared: {settings['cookie_path']}")

#!/usr/bin/env python3
"""
Image Generator - WeChat Director v2.2.8
Automated "Generate-Compress-Upload-Inject" Pipeline

Usage:
    python3 visualize.py --brief path/to/Storyboard.md --draft path/to/Draft.md
"""

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import time
import hashlib
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Optional dependencies
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logger.warning("⚠️ Pillow not installed. Image stitching will be skipped.")

try:
    import tinify
    TINIFY_AVAILABLE = True
except ImportError:
    TINIFY_AVAILABLE = False
    logger.warning("⚠️ tinify not installed. Compression will be skipped.")

try:
    from qcloud_cos import CosConfig
    from qcloud_cos import CosS3Client
    COS_AVAILABLE = True
except ImportError:
    COS_AVAILABLE = False
    logger.warning("⚠️ cos-python-sdk-v5 not installed. Upload will be skipped.")


# --- Configurations & Constants ---

def run_obsidian_cmd(args):
    """Run an obsidian CLI command and return success status and output."""
    try:
        if shutil.which("obsidian") is None:
            return False, "obsidian CLI not found in PATH"
            
        # Execute the actual command
        # Obsidian 1.12.7 CLI uses positional KV pairs like name=val path=path
        result = subprocess.run(["obsidian"] + args, capture_output=True, text=True, check=True)
        
        # CRITICAL: Obsidian CLI often exits with 0 even on error.
        output = (result.stdout + result.stderr).strip()
        if "Error:" in output or "not found" in output or "Missing required parameter" in output:
            return False, output
            
        return True, output
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False, ""

def get_obsidian_vault_root(start_path=None):
    """Get the real Obsidian vault root by looking for the .obsidian configuration folder."""
    if start_path is None:
        start_path = Path(__file__).resolve()
        
    current = start_path
    while current.parent != current:
        if (current / ".obsidian").is_dir():
            return current
        current = current.parent
        
    # Fallback: Assume repo root is vault root
    return get_workspace_root().resolve()

def get_obsidian_path(abs_path):
    """Convert absolute path to vault-relative path for Obsidian CLI."""
    # Obsidian CLI expects paths RELATIVE to the REAL vault root.
    vault_root = get_obsidian_vault_root()
    try:
        # Ensure we are working with absolute resolved paths
        target_path = Path(abs_path).resolve()
        rel_path = target_path.relative_to(vault_root)
        return str(rel_path)
    except Exception:
        # If path is not under vault_root, return as is (Obsidian will likely fail anyway)
        return str(abs_path)

def is_obsidian_reachable(file_path):
    """Check if a file path is located within the current Obsidian vault."""
    vault_root = get_obsidian_vault_root()
    try:
        Path(file_path).resolve().relative_to(vault_root)
        return True
    except (ValueError, RuntimeError):
        return False

def set_obsidian_properties(file_path, properties):
    """Set multiple properties using Obsidian CLI."""
    if not is_obsidian_reachable(file_path):
        return False
        
    rel_path = get_obsidian_path(file_path)
    success_count = 0
    total_props = len([v for v in properties.values() if v is not None])
    
    for key, value in properties.items():
        if value is None: continue
        # Format: property:set name=key value=val path=path
        val_str = json.dumps(value) if isinstance(value, list) else str(value)
        
        # Use Obsidian 1.12 syntax: property:set name=... value=... path=...
        cmd_args = ["property:set", f"name={key}", f"value={val_str}", f"path={rel_path}"]
        ok, err = run_obsidian_cmd(cmd_args)
        if ok:
            success_count += 1
        else:
            logger.warning(f"⚠️ CLI Property set failed for {key}: {err}")
            
    return success_count == total_props

def obsidian_open(file_path):
    """Open a file in Obsidian GUI."""
    if not is_obsidian_reachable(file_path):
        return False
        
    rel_path = get_obsidian_path(file_path)
    # Use Obsidian 1.12 syntax: open path=...
    ok, err = run_obsidian_cmd(["open", f"path={rel_path}"])
    if not ok:
        logger.warning(f"⚠️ CLI Open failed: {err}")
    return ok

ASPECT_RATIOS = {
    "cover-main": {"width": 1504, "height": 640, "suffix": "cover-main"},
    "cover-sidebar": {"width": 1024, "height": 1024, "suffix": "cover-sidebar"},
    "illustration": {"width": 768, "height": 1024, "suffix": "illustration"},
    "quote": {"width": 768, "height": 1024, "suffix": "quote"},
}
DIRECTOR_VERSION = "2.2.8"

def get_workspace_root():
    """Find the workspace root: the parent of the repo (contains David-Writing-Team and conductor/ as siblings)."""
    script_dir = Path(__file__).resolve().parent
    # scripts -> wechat-director -> Skills -> David-Writing-Team -> parent
    repo_root = script_dir.parent.parent.parent  # David-Writing-Team/
    return repo_root.parent  # parent that contains both David-Writing-Team and conductor

def get_skill_root():
    """Find the wechat-director skill root directory."""
    return Path(__file__).resolve().parent.parent

def load_api_config():
    """Load API keys from conductor/api_keys.json"""
    config_path = get_workspace_root() / "conductor" / "api_keys.json"
    if not config_path.exists():
        logger.warning("⚠️ API Config not found. API providers, compression, and upload may be unavailable.")
        return {}

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    return config

# --- Helper Functions ---

def sanitize_filename(text):
    text = re.sub(r'[<>:"/\\|?*]', '', text)
    text = re.sub(r'\s+', '-', text)
    return text[:50]

def clean_prompt(prompt):
    prompt = prompt.strip()
    if len(prompt) < 5: return None
    prompt = re.sub(r',?\s*aspect ratio\s*[\d.:]+', '', prompt, flags=re.IGNORECASE)
    prompt = re.sub(r'\s--\w+(?:\s+[\w.:]+)?', '', prompt)
    return prompt.strip()

def check_ip_requirement(text):
    return bool(re.search(r'(?:IP(?:形象)?|Reference|参考图?)\s*[:：]\s*(?:Yes|True|是|On|Required|1)', text, re.IGNORECASE))

def calculate_hash(prompt, width, height, model, use_ip=False):
    content = f"{prompt}|{width}|{height}|{model}|{use_ip}"
    return hashlib.md5(content.encode('utf-8')).hexdigest()[:8]

def require_config(api_config, provider_name, required_keys):
    if not api_config:
        raise RuntimeError(f"{provider_name} config missing.")

    missing = [key for key in required_keys if not api_config.get(key)]
    if missing:
        missing_str = ", ".join(missing)
        raise RuntimeError(f"{provider_name} config incomplete: missing {missing_str}.")

def resolve_gemini_web_settings(api_config):
    repo_root = get_workspace_root()
    skill_root = get_skill_root()
    provider_config = api_config.get("gemini_web", {})
    runtime_dir = Path(provider_config.get(
        "runtime_dir",
        repo_root / ".gemini" / "wechat-director" / "gemini-web"
    ))

    return {
        "model": provider_config.get("model", "gemini-3-pro"),
        "timeout": int(provider_config.get("timeout", 240)),
        "script_dir": skill_root / "vendor" / "baoyu-danger-gemini-web" / "scripts",
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

def extract_context(text_block):
    match = re.search(r'>\s*Context\s*[:：]\s*["“](.*?)["”]', text_block, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    match = re.search(r'>\s*Context\s*[:：]\s*(.+)', text_block, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None

def parse_visual_brief(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Base title from filename
    filename_title = sanitize_filename(Path(file_path).stem)
    title = filename_title

    # 2. Fallback: If filename is generic "Storyboard", use parent directory name (Project Name)
    if title.lower() == "storyboard":
        parent_dir = Path(file_path).parent.name
        if parent_dir:
            title = sanitize_filename(parent_dir)

    # 3. Override: Explicit frontmatter title has highest priority
    fm_match = re.search(r'^title:\s*"(.+?)"', content, re.MULTILINE)
    if fm_match:
        title = sanitize_filename(fm_match.group(1))

    tasks = []

    # 1. Main Cover
    if "cover-main" in content or "主视觉" in content:
        section_match = re.search(r'###\s*Part\s*A[:：][^\n]*主视觉.*?(?=###\s*Part\s*B|##|\Z)', content, re.DOTALL | re.IGNORECASE)
        if section_match:
            section_text = section_match.group(0)
            prompt_match = re.search(r'```(?:\w+)?\n(.*?)```', section_text, re.DOTALL)
            if prompt_match:
                prompt = clean_prompt(prompt_match.group(1))
                if prompt:
                    dims = ASPECT_RATIOS["cover-main"]
                    tasks.append({
                        "type": "cover-main", "prompt": prompt,
                        "width": dims["width"], "height": dims["height"],
                        "suffix": "cover-main",
                        "use_ip": check_ip_requirement(section_text),
                        "context": None
                    })

    # 2. Sidebar Cover
    if "cover-sidebar" in content or "侧边栏" in content:
        section_match = re.search(r'###\s*Part\s*B[:：][^\n]*侧边栏.*?(?=##|\Z)', content, re.DOTALL | re.IGNORECASE)
        if section_match:
            section_text = section_match.group(0)
            prompt_match = re.search(r'```(?:\w+)?\n(.*?)```', section_text, re.DOTALL)
            if prompt_match:
                prompt = clean_prompt(prompt_match.group(1))
                if prompt:
                    dims = ASPECT_RATIOS["cover-sidebar"]
                    tasks.append({
                        "type": "cover-sidebar", "prompt": prompt,
                        "width": dims["width"], "height": dims["height"],
                        "suffix": "cover-sidebar",
                        "use_ip": check_ip_requirement(section_text),
                        "context": None
                    })

    # 3. In-article Illustrations
    illustration_count = 0
    for match in re.finditer(r'###\s*Part\s*C[:：][^\n]*内文配图.*?(?=###\s*Part\s*[A-Z]|\Z)', content, re.DOTALL | re.IGNORECASE):
        section_text = match.group(0)
        for block in re.finditer(r'####\s*插图\s*\d+.*?(?=####\s*插图|##|\Z)', section_text, re.DOTALL):
            block_text = block.group(0)

            # Extract Description
            desc_match = re.match(r'####\s*插图\s*\d+[:：]?\s*(.*)', block_text)
            description = ""
            if desc_match:
                description = re.sub(r'[<>:"/\\|?*]', '', desc_match.group(1)).strip()

            prompt_match = re.search(r'```(?:\w+)?\n(.*?)```', block_text, re.DOTALL)
            if not prompt_match: continue

            prompt = clean_prompt(prompt_match.group(1))
            if not prompt: continue

            illustration_count += 1
            dims = ASPECT_RATIOS["illustration"]
            context = extract_context(block_text)

            tasks.append({
                "type": "illustration",
                "prompt": prompt,
                "width": dims["width"],
                "height": dims["height"],
                "suffix": f"illustration-{illustration_count:02d}",
                "use_ip": check_ip_requirement(block_text),
                "context": context,
                "description": description
            })

    return title, tasks

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
        script_dir = Path(__file__).resolve().parent
        ip_image_path = script_dir.parent / "assets" / "IP_Reference.png"
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
        ip_image_path = Path(__file__).resolve().parent.parent / "assets" / "IP_Reference.png"
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

def submit_task_siliconflow(api_config, prompt, width, height):
    require_config(api_config, "SiliconFlow", ["base_url", "model", "api_key"])
    url = f"{api_config['base_url']}images/generations"
    headers = {"Authorization": f"Bearer {api_config['api_key']}", "Content-Type": "application/json"}
    payload = {
        "model": api_config["model"], "prompt": prompt,
        "image_size": f"{int(width)}x{int(height)}", "batch_size": 1,
        "num_inference_steps": 20, "guidance_scale": 3.5
    }

    req = urllib.request.Request(url, headers=headers, data=json.dumps(payload).encode('utf-8'))
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.load(resp)
            if "data" in data and len(data["data"]) > 0: return data["data"][0]["url"]
            raise RuntimeError(f"Unexpected response: {data}")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"SiliconFlow failed ({e.code}): {e.read().decode('utf-8', errors='replace')[:200]}...") from e

def submit_task_gpt_image2(api_config, prompt, width, height, use_ip=False):
    """Generate image via gpt-image-2 using OpenAI-compatible endpoint."""
    require_config(api_config, "GPT-Image2", ["base_url", "model", "api_key"])

    url = f"{api_config['base_url'].rstrip('/')}/images/generations"
    headers = {
        "Authorization": f"Bearer {api_config['api_key']}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": api_config["model"],
        "prompt": prompt,
        "size": f"{int(width)}x{int(height)}",
        "n": 1,
        "response_format": "b64_json"
    }

    req = urllib.request.Request(url, headers=headers, data=json.dumps(payload).encode('utf-8'))
    max_retries = 1
    for attempt in range(max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                data = json.load(resp)
                if "data" in data and len(data["data"]) > 0:
                    return data["data"][0]["b64_json"]
                raise RuntimeError(f"Unexpected response: {str(data)[:200]}")
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', errors='replace')
            if (e.code == 429 or 500 <= e.code < 600) and attempt < max_retries:
                logger.info(f"[GPT-Image2] Error {e.code}, retrying...")
                time.sleep(3)
                continue
            raise RuntimeError(f"GPT-Image2 failed ({e.code}): {body[:200]}...") from e

# --- Pipeline Class ---

class VisualPipeline:
    def __init__(self, api_config, output_dir, force=False):
        self.config = api_config
        self.output_dir = output_dir
        self.force = force
        self.manifest_path = output_dir / "manifest.json"
        self.manifest = self._load_manifest()

        if TINIFY_AVAILABLE and "tinify" in self.config and self.config["tinify"].get("api_key"):
            tinify.key = self.config["tinify"]["api_key"]
            self.compress_enabled = True
        else:
            self.compress_enabled = False

        if COS_AVAILABLE and "cos" in self.config:
            cos_conf = self.config["cos"]
            required_keys = ["region", "secret_id", "secret_key", "bucket"]
            if all(k in cos_conf and cos_conf[k] for k in required_keys):
                self.cos_config = CosConfig(
                    Region=cos_conf["region"],
                    SecretId=cos_conf["secret_id"],
                    SecretKey=cos_conf["secret_key"]
                )
                self.cos_client = CosS3Client(self.cos_config)
                self.bucket = cos_conf["bucket"]
                self.cdn_domain = cos_conf.get("cdn_domain", "")
                self.upload_enabled = True
            else:
                logger.warning(f"⚠️ COS config incomplete. Upload disabled.")
                self.upload_enabled = False
        else:
            self.upload_enabled = False

    def _resolve_providers(self, provider):
        if provider != "auto":
            return [provider]

        providers = []

        if self.config.get("gemini"):
            providers.append("gemini")
        if self.config.get("gpt-image2"):
            providers.append("gpt-image2")

        return providers

    def _load_manifest(self):
        if self.manifest_path.exists():
            try:
                with open(self.manifest_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except: pass
        return {}

    def _save_manifest(self):
        try:
            with open(self.manifest_path, "w", encoding="utf-8") as f:
                json.dump(self.manifest, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"⚠️ Failed to save manifest: {e}")

    def _enforce_ratio(self, img_path, target_w, target_h):
        """Deterministically force image to target dimensions (Aspect Fill + Top-Weighted Crop)."""
        if not PIL_AVAILABLE or not img_path.exists(): return False

        try:
            with Image.open(img_path) as img:
                src_w, src_h = img.size
                if (src_w, src_h) == (target_w, target_h):
                    return False

                logger.info(f"✂️  Enforcing {target_w}x{target_h} for {img_path.name}...")

                # Aspect Fill logic
                scale_w = target_w / src_w
                scale_h = target_h / src_h
                scale = max(scale_w, scale_h)

                new_w = int(src_w * scale)
                new_h = int(src_h * scale)
                img_resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

            # Top-Weighted Crop
            diff_w = new_w - target_w
            diff_h = new_h - target_h

            left = diff_w / 2
            top = diff_h * 0.2 # Bias: keep top 20% visible, cut mostly from bottom
            right = left + target_w
            bottom = top + target_h

            img_final = img_resized.crop((left, top, right, bottom))
            img_final.save(img_path, quality=95)
            return True

        except Exception as e:
            logger.warning(f"⚠️ Ratio enforcement failed: {e}")
            return False

    def generate(self, task, title, provider="auto"):
        # Cover files use simple names (deleted after publish); illustrations keep title prefix
        if task['suffix'].startswith("cover"):
            local_filename = f"{task['suffix']}.jpg"
        else:
            local_filename = f"{title}-{task['suffix']}.jpg"
        local_path = self.output_dir / local_filename

        providers = self._resolve_providers(provider)
        if not providers:
            logger.error("❌ No available providers. Check gemini-web vendor or API config.")
            return None, local_path

        preferred_provider = providers[0]
        current_hash = calculate_hash(
            task['prompt'],
            task['width'],
            task['height'],
            preferred_provider,
            task.get('use_ip', False)
        )

        cached = self.manifest.get(task['suffix'], {})

        # URL Cache Hit
        if (
            not self.force and
            cached.get("hash") == current_hash and
            cached.get("provider") == preferred_provider and
            cached.get("url")
        ):
            logger.info(f"⏭️  [Cache Hit] {task['suffix']} -> {cached['url']}")
            # Safety Net: Enforce Ratio on Cached Cover Main
            if task['type'] == 'cover-main':
                 if self._enforce_ratio(local_path, task['width'], task['height']):
                     cached["compressed"] = False
            return cached['url'], local_path

        # Local File Cache Hit
        generated_new = False
        if (
            not self.force and
            local_path.exists() and
            cached.get("hash") == current_hash and
            cached.get("provider") == preferred_provider
        ):
             logger.info(f"📂 [Local Hit] {task['suffix']} exists.")
             # Safety Net: Enforce Ratio on Cached Cover Main (Local Hit)
             if task['type'] == 'cover-main':
                 if self._enforce_ratio(local_path, task['width'], task['height']):
                     cached["compressed"] = False
        else:
            # Generate new image
            logger.info(f"🎨 Generating {task['suffix']}...")
            success = False

            # Determine Ratio Suffix for Gemini
            # ratio_suffix = ""  # Disabled: model doesn't support suffixed model names
            ratio_suffix = ""

            provider_used = None

            for p in providers:
                try:
                    if p == "gemini":
                        b64 = submit_task_gemini(self.config["gemini"], task['prompt'], task['width'], task['height'], task.get('use_ip', False), ratio_suffix)
                        with open(local_path, "wb") as f: f.write(base64.b64decode(b64))
                        provider_used = p
                        success = True
                        break
                    if p == "gpt-image2":
                        b64 = submit_task_gpt_image2(self.config["gpt-image2"], task['prompt'], task['width'], task['height'], task.get('use_ip', False))
                        with open(local_path, "wb") as f: f.write(base64.b64decode(b64))
                        provider_used = p
                        success = True
                        break
                except Exception as e:
                    logger.error(f"❌ {p} failed: {e}")

            if not success:
                logger.error(f"❌ Failed to generate {task['suffix']}")
                return None, local_path

            # Safety Net: Enforce Ratio on New Cover Main
            if task['type'] == 'cover-main':
                 if self._enforce_ratio(local_path, task['width'], task['height']):
                     cached["compressed"] = False

            generated_new = True

        # COMPRESS
        if self.compress_enabled and local_path.exists() and (generated_new or not cached.get("compressed")):
            try:
                logger.info(f"🗜️  Compressing {local_filename}...")
                source = tinify.from_file(str(local_path))
                source.to_file(str(local_path))
                cached["compressed"] = True
            except Exception as e:
                logger.warning(f"⚠️ Compression failed: {e}")

        # UPLOAD (Illustrations only)
        final_url = None
        if self.upload_enabled and local_path.exists() and "cover" not in task['type']:
            date_suffix = datetime.now().strftime("%Y%m%d")
            # Filename: {Project}_{Suffix}_{Hash}_{Date}.jpg (Flat structure in 'wechat/' folder)
            cos_filename = f"{title}_{task['suffix']}_{current_hash}_{date_suffix}.jpg"
            cos_key = f"wechat/{cos_filename}"
            try:
                logger.info(f"☁️  Uploading to COS: {cos_key}")
                self.cos_client.put_object_from_local_file(Bucket=self.bucket, LocalFilePath=str(local_path), Key=cos_key)
                if self.cdn_domain:
                    final_url = f"{self.cdn_domain.rstrip('/')}/{cos_key}"
                else:
                    final_url = self.cos_config.uri(self.bucket, cos_key)
                logger.info(f"✅ Uploaded: {final_url}")
            except Exception as e:
                logger.error(f"❌ Upload failed: {e}")

        if not final_url and cached.get("hash") == current_hash and cached.get("url"):
            final_url = cached["url"]

        self.manifest[task['suffix']] = {
            "hash": current_hash,
            "provider": cached.get("provider", preferred_provider) if not generated_new else provider_used,
            "prompt": task['prompt'],
            "updated_at": time.time(),
            "url": final_url,
            "compressed": cached.get("compressed", False)
        }
        self._save_manifest()

        return final_url, local_path

    def inject(self, draft_path, task, image_url):
        if not draft_path or not draft_path.exists(): return False
        if not task.get("context") or not image_url: return False

        context_sent = task["context"]
        logger.info(f"💉 Injecting {task['suffix']}...")

        with open(draft_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        matches = []
        for i, line in enumerate(lines):
            if context_sent in line:
                matches.append(i)

        if len(matches) == 0:
            logger.warning(f"⚠️ Injection Skipped: Context not found -> '{context_sent[:30]}...'")
            return False
        elif len(matches) > 1:
            logger.error(f"❌ Injection Failed: Context ambiguous ({len(matches)} matches) -> '{context_sent[:30]}...'")
            return False

        match_index = matches[0]
        # Fix: Ensure fallback to suffix if description is empty string (Falsey)
        alt_text = task.get("description") or task['suffix']

        existing_line_idx = -1
        is_exact_match = False

        for j in range(1, 10):
            if match_index + j < len(lines):
                idx = match_index + j
                line_content = lines[idx]
                img_match = re.search(r'!\[(.*?)\]\((.*?)\)', line_content)
                if img_match:
                    current_alt = img_match.group(1)
                    current_url = img_match.group(2)
                    if task['suffix'] in current_url:
                        existing_line_idx = idx
                        if image_url.strip() in current_url and current_alt.strip() == alt_text.strip():
                            is_exact_match = True
                        break

        if is_exact_match:
            logger.info("   ⏭️  Image already up-to-date, skipping.")
        elif existing_line_idx != -1:
            logger.info(f"   🔄 Updating stale link at line {existing_line_idx+1}...")
            lines[existing_line_idx] = f"![{alt_text}]({image_url})\n"
            with open(draft_path, "w", encoding="utf-8") as f:
                f.writelines(lines)
        else:
            img_md = f"\n![{alt_text}]({image_url})\n"
            lines.insert(match_index + 1, img_md)
            with open(draft_path, "w", encoding="utf-8") as f:
                f.writelines(lines)
            logger.info("   ✅ Injected successfully.")

        return True

def stitch_covers(output_dir, title):
    if not PIL_AVAILABLE: return
    main_path = output_dir / "cover-main.jpg"
    sidebar_path = output_dir / "cover-sidebar.jpg"
    combined_path = output_dir / "cover-combined.jpg"

    if not main_path.exists() or not sidebar_path.exists(): return

    try:
        img_main = Image.open(main_path)
        img_sidebar = Image.open(sidebar_path)
        target_height = img_sidebar.height
        aspect = img_main.width / img_main.height
        new_width = int(target_height * aspect)
        img_main_resized = img_main.resize((new_width, target_height), Image.Resampling.LANCZOS)

        combined = Image.new('RGB', (new_width + img_sidebar.width, target_height))
        combined.paste(img_main_resized, (0, 0))
        combined.paste(img_sidebar, (new_width, 0))
        combined.save(combined_path, quality=95)
        logger.info(f"🖼️  Stitched Cover: {combined_path}")
    except Exception as e:
        logger.error(f"❌ Stitching failed: {e}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--brief", help="Path to Storyboard.md")
    parser.add_argument("--draft", help="Path to Draft.md for injection")
    parser.add_argument("--output-dir")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--provider", default="auto", choices=["auto", "gemini-web", "gemini", "gpt-image2"])
    parser.add_argument("--gemini-web-login", action="store_true", help="Initialize Gemini Web login, then exit")
    args = parser.parse_args()

    try:
        api_config = load_api_config()
    except Exception as e:
        logger.error(str(e))
        return

    if args.gemini_web_login:
        try:
            login_gemini_web(api_config)
        except Exception as e:
            logger.error(str(e))
        return

    if not args.brief:
        logger.error("--brief is required unless --gemini-web-login is used.")
        return

    brief_path = Path(args.brief)
    if not brief_path.exists():
        logger.error(f"File not found: {brief_path}")
        return

    output_dir = Path(args.output_dir) if args.output_dir else brief_path.parent / "img"
    output_dir.mkdir(parents=True, exist_ok=True)

    title, tasks = parse_visual_brief(brief_path)
    if not tasks:
        logger.warning("No tasks found.")
        return

    pipeline = VisualPipeline(api_config, output_dir, force=args.force)

    print(f"🎬 Director v{DIRECTOR_VERSION} starting for '{title}'")
    print(f"   Tasks: {len(tasks)} | Provider: {args.provider}")
    print(f"   Compression: {'ON' if pipeline.compress_enabled else 'OFF'}")
    print(f"   Upload: {'ON' if pipeline.upload_enabled else 'OFF'}")
    print("-" * 40)

    for task in tasks:
        url, local_path = pipeline.generate(task, title, provider=args.provider)

        injection_done = False
        if args.draft and url and task.get("context"):
            injection_done = pipeline.inject(Path(args.draft), task, url)
        elif not args.draft:
            logger.info(f"ℹ️  Skipping injection (no draft provided). Local file retained: {local_path.name}")
        elif not task.get("context"):
             logger.warning(f"⚠️ Skipping injection (missing context). Local file retained: {local_path.name}")

        if url and "cover" not in task['type'] and injection_done:
            try:
                if local_path.exists():
                    local_path.unlink()
                    logger.info(f"🗑️  Cleanup: Deleted local file {local_path.name}")
            except Exception as e:
                logger.warning(f"⚠️ Cleanup failed: {e}")

    stitch_covers(output_dir, title)
    
    # --- Obsidian CLI Enhancements ---
    cli_ok = shutil.which("obsidian") is not None
    if cli_ok and args.draft:
        draft_p = Path(args.draft)
        if draft_p.exists() and is_obsidian_reachable(draft_p):
            # 1. Set property (Verify result)
            if set_obsidian_properties(draft_p, {"visual_ready": True}):
                logger.info(f"🏷️  Marked 'visual_ready: true' in {draft_p.name}")
                # 2. Open in GUI for preview
                if obsidian_open(draft_p):
                    logger.info(f"🚀 Focus jumping to Obsidian for preview: {draft_p.name}")
            else:
                logger.warning(f"⚠️ Failed to mark 'visual_ready' in {draft_p.name} via CLI.")

    print("-" * 40)
    print("✅ Director finished.")

if __name__ == "__main__":
    main()

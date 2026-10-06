#!/usr/bin/env python3
"""
Image Generator - WeChat Director
Automated "Generate-Compress-Upload-Inject" Pipeline

Usage:
    python3 visualize.py --brief path/to/Storyboard.md --draft path/to/Draft.md

退出码（供 Agent / 脚本判断成败）
--------------------------------
    0  全部任务成功产出
    1  运行期失败：配置读不到、brief 文件不存在、没有任何任务、
       或有任务最终没产出（生成失败 / 上传失败 / 注入失败）
    2  用法错误：缺少 --brief 等（与 argparse 自身的约定一致）

注意：0 不代表"全部成功"以外的含义 —— 只要有任何一张图没产出，就是 1。
"""
import argparse
import base64
import json
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

# 让本文件以任意方式被加载时，都能找到同目录的兄弟模块
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from console_encoding import configure_console

configure_console()

from director_core import (DIRECTOR_VERSION, calculate_hash, get_workspace_root,
                           load_api_config, logger)
from brief_parser import parse_visual_brief
from obsidian_bridge import (is_obsidian_reachable, obsidian_open,
                             set_obsidian_properties)
from providers.gemini import (login_gemini_web, submit_task_gemini,
                              submit_task_gemini_web)
from providers.gpt_image2 import submit_task_gpt_image2
# 注：providers/siliconflow.py 仍存在，但**没有任何 CLI 或 auto 路径能选中它**
# （不在 --provider choices、不在 _resolve_providers）。原先是"导入但从不调用"
# 的死代码，容易让人误以为该渠道可用，故移除导入。若将来要启用，需同时补
# choices / auto 解析 / 分发分支三处。

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

# --- Pipeline Class ---

class VisualPipeline:
    def __init__(self, config, output_dir, force=False, upload_only=False):
        self.config = config
        self.output_dir = output_dir
        self.force = force
        self.upload_only = upload_only
        self.manifest_path = output_dir / "manifest.json"
        self.manifest = self._load_manifest()

        # 本轮未产出的任务（suffix -> 原因）。generate() 失败时**不抛异常**，
        # 只返回 (None, local_path)，所以必须显式记账，否则 main() 无法判断
        # 「是不是每张图都失败了」，只能一律以退出码 0 收场。
        self.failures = {}

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

        if self.config.get("gpt-image2"):
            providers.append("gpt-image2")
        if self.config.get("gemini"):
            providers.append("gemini")

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
            if img_final.mode != "RGB":
                img_final = img_final.convert("RGB")
            img_final.save(img_path, quality=95)
            return True

        except Exception as e:
            logger.warning(f"⚠️ Ratio enforcement failed: {e}")
            return False

    def generate(self, task, title, provider="auto"):
        # Cover files use simple names (deleted after publish); illustrations keep title prefix
        if task['suffix'].startswith("cover"):
            local_filename = f"{task['suffix']}.jpg"
            local_path = self.output_dir / local_filename
        else:
            local_filename = f"{title}-{task['suffix']}.jpg"
            local_path = self.output_dir / local_filename
            # Fallback: check flat filename without title prefix (e.g. illustration-01.jpg)
            if not local_path.exists():
                alt_path = self.output_dir / f"{task['suffix']}.jpg"
                if alt_path.exists():
                    local_path = alt_path
                    local_filename = alt_path.name

        providers = self._resolve_providers(provider)
        if not providers and not self.upload_only:
            logger.error("❌ No available providers. Check gemini-web vendor or API config.")
            self.failures[task['suffix']] = "无可用 provider"
            return None, local_path

        preferred_provider = providers[0] if providers else "local"
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
            not self.upload_only and
            cached.get("hash") == current_hash and
            cached.get("provider") == preferred_provider and
            cached.get("url")
        ):
            logger.info(f"⏭️  [Cache Hit] {task['suffix']} -> {cached['url']}")
            if self._enforce_ratio(local_path, task['width'], task['height']):
                cached["compressed"] = False
            return cached['url'], local_path

        # Local File Cache Hit or Upload Only Mode
        generated_new = False
        if self.upload_only:
            if not local_path.exists():
                logger.warning(f"⚠️ [Upload Only] Local file not found: {local_path.name} in {self.output_dir}")
                self.failures[task['suffix']] = "upload-only 模式下本地文件缺失"
                return None, local_path
            logger.info(f"📂 [Upload Only] Found local file: {local_path.name}")
        elif (
            not self.force and
            local_path.exists() and
            cached.get("hash") == current_hash and
            cached.get("provider") == preferred_provider
        ):
             logger.info(f"📂 [Local Hit] {task['suffix']} exists.")
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
                        image_bytes = submit_task_gpt_image2(self.config["gpt-image2"], task['prompt'], task['width'], task['height'], task.get('use_ip', False))
                        with open(local_path, "wb") as f:
                            f.write(image_bytes)
                        provider_used = p
                        success = True
                        break
                    if p == "gemini-web":
                        # 契约与上面两个不同：直接写入 local_path、返回 None，失败抛异常。
                        # 整个 api_config 传进去（函数内部自己取 "gemini_web" 段）。
                        submit_task_gemini_web(
                            self.config, task['prompt'], local_path,
                            task.get('use_ip', False))
                        provider_used = p
                        success = True
                        break
                    # 走到这里 = --provider 广告了某个值、却没有对应分发分支。
                    # 以前这种落空只会报笼统的「Failed to generate」，看不到真因
                    # （gemini-web 就曾长期如此：--help 里有、分发里没有）。
                    raise ValueError(
                        f"provider '{p}' 缺少分发分支 —— 若是新增渠道，"
                        "需同时补 _resolve_providers 与 generate() 里的分支")
                except Exception as e:
                    logger.error(f"❌ {p} failed: {e}")

            if not success:
                logger.error(f"❌ Failed to generate {task['suffix']}")
                self.failures[task['suffix']] = (
                    f"生成失败（已尝试: {', '.join(providers) or '无'}）")
                return None, local_path

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

        # 该上传的任务（非封面，且上传已启用）最终仍拿不到 URL → 记为失败。
        # 放在缓存回退**之后**判断，避免"上传失败但有缓存 URL"被误报为失败。
        if (self.upload_enabled and local_path.exists()
                and "cover" not in task['type'] and not final_url):
            self.failures[task['suffix']] = "无可用图片 URL（上传失败且无缓存）"

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
            lines[existing_line_idx] = f"![{alt_text}|400]({image_url})\n"
            with open(draft_path, "w", encoding="utf-8") as f:
                f.writelines(lines)
        else:
            img_md = f"\n![{alt_text}|400]({image_url})\n"
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


def _provider_status(api_config):
    """列出 api_keys.json 里已配置的生图渠道（只读，不生成、不收费）。"""
    providers = []
    for name, conf in (api_config or {}).items():
        if not isinstance(conf, dict):
            continue
        if name in ("tinify", "cos"):
            continue
        has_key = bool(conf.get("api_key"))
        providers.append({
            "provider": name,
            "configured": bool(conf.get("base_url") or conf.get("model") or has_key),
            "has_api_key": has_key,
            "base_url": conf.get("base_url", ""),
            "model": conf.get("model", ""),
            "adapter": conf.get("adapter", ""),
        })
    return providers


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--brief", help="Path to Storyboard.md")
    parser.add_argument("--draft", help="Path to Draft.md for injection")
    parser.add_argument("--output-dir")
    parser.add_argument("--workspace", help="文章工作区根（显式指定，规避自动检测歧义）")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--upload-only", action="store_true", help="Skip image generation; compress, upload local images to COS, and inject into draft")
    parser.add_argument("--provider", default="auto", choices=["auto", "gemini-web", "gemini", "gpt-image2"])
    parser.add_argument("--list-providers", action="store_true", help="仅输出已配置 provider 状态 JSON（不生成、不收费）")
    parser.add_argument("--gemini-web-login", action="store_true", help="Initialize Gemini Web login, then exit")
    args = parser.parse_args()

    try:
        api_config = load_api_config(explicit=args.workspace)
    except Exception as e:
        logger.error(str(e))
        sys.exit(1)

    if args.list_providers:
        workspace_root = get_workspace_root(explicit=args.workspace)
        print(json.dumps(
            {"workspace": str(workspace_root or ""),
             "providers": _provider_status(api_config)},
            ensure_ascii=False, indent=2))
        return

    if args.gemini_web_login:
        try:
            login_gemini_web(api_config)
        except Exception as e:
            logger.error(str(e))
            sys.exit(1)
        return

    if not args.brief:
        logger.error("--brief is required unless --gemini-web-login is used.")
        sys.exit(2)

    brief_path = Path(args.brief)
    if not brief_path.exists():
        logger.error(f"File not found: {brief_path}")
        sys.exit(1)

    output_dir = Path(args.output_dir) if args.output_dir else brief_path.parent / "zpicture.assets"
    output_dir.mkdir(parents=True, exist_ok=True)

    title, tasks = parse_visual_brief(brief_path)
    if not tasks:
        logger.error(
            f"No tasks found in {brief_path.name} —— 未产出任何图片，按失败处理。")
        sys.exit(1)

    pipeline = VisualPipeline(api_config, output_dir, force=args.force, upload_only=args.upload_only)

    print(f"🎬 Director v{DIRECTOR_VERSION} starting for '{title}'")
    print(f"   Tasks: {len(tasks)} | Mode: {'Upload Only (Skip Gen)' if args.upload_only else f'Provider: {args.provider}'}")
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

        # 该注入却没注入成功（draft 给了、图有 URL、也有 context）→ 记为失败。
        if args.draft and url and task.get("context") and not injection_done:
            pipeline.failures[task['suffix']] = "注入 draft 失败"

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

    # 有任务没产出 → 明确汇总并非 0 退出。
    # 修补的原因：generate() 失败时不抛异常、只返回 (None, local_path)，
    # 原先即使每一张图都失败，也会照常打印「✅ Director finished.」并以 0 退出，
    # Agent 侧靠退出码判断成败时会误判为成功。
    if pipeline.failures:
        print(f"❌ Director finished with {len(pipeline.failures)} failed task(s):")
        for suffix, reason in pipeline.failures.items():
            print(f"   · {suffix}: {reason}")
        sys.exit(1)

    print("✅ Director finished.")


if __name__ == "__main__":
    main()

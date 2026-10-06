#!/usr/bin/env python3
"""WeChat Director —— SiliconFlow 生图适配器。"""
import base64
import json
import time
import urllib.error
import urllib.request

from director_core import require_config

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

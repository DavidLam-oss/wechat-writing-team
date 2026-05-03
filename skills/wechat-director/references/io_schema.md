# WeChat Director I/O Schema

## 📁 输入规范 (Input)

1.  **Draft Article (`02_Draft.md`)**
    *   完整 Markdown 正文内容。
    *   或已归档的 `published/[Title].md`。
    *   用途：提取画面意境、IP 出现的场景。

## 📄 输出规范 (Output)

### 1. Storyboard (`Storyboard.md`)

*   **Path**: 与 Input 同级目录（或指定目录）。
*   **Format**: Strict Markdown Structure (for script parsing).

```markdown
## Visual Storyboard

### Part A: 主视觉 cover-main (2.35:1)
(IP形象: 是)
```
[中文 Prompt: 场景描述, IP特征...]
```

### Part B: 侧边栏 cover-sidebar (1:1)
(IP形象: 否)
```
[中文 Prompt: 纯色背景 + 总结文字...]
```

### Part C: 内文配图 illustration
#### 插图 1: ...
(IP形象: 是)
```
[中文 Prompt: 动作描述...]
```
> Context: "原文上一段落的最后一句（用于定位插入点）"
```

## 🛠️ 脚本契约 (`scripts/visualize.py`)

*   **Invoke**: Manual trigger by user or Agent.
*   **Input**:
    *   `--brief`: `Storyboard.md` (Must match Regex above).
    *   `--draft`: `02_Draft.md` (Required for Injection & Cleanup).
*   **Logic**:
    1.  **Parse**: Reads tasks and IP flags from Storyboard.
    2.  **Health Check**: When `gemini-web` is preferred, validates login state first; if unavailable in `auto` mode, skips to fallback providers.
    3.  **Generate**: Calls `gemini-web` first, then falls back to Gemini API / SiliconFlow API (injects IP ref if needed).
        *   When `gemini-web` is selected as the preferred provider, missing images in the same article are batch-generated through one Gemini Web session before per-image post-processing.
    4.  **Compress**: Optimizes images via TinyPNG (if configured).
    5.  **Upload**: Puts illustrations to Tencent COS (if configured). covers stay local.
    6.  **Inject**: Inserts COS URLs into `Draft.md` after the `Context` sentence.
    7.  **Cleanup**: Deletes local copies of uploaded & injected illustrations.
*   **Provider Notes**:
    *   `--provider auto`: `gemini-web` → `gemini` → `siliconflow`
    *   `--gemini-web-login`: opens isolated Gemini Web login flow and exits
    *   `gemini-web` health check: validates cached login before generation; `auto` mode skips unhealthy `gemini-web`
    *   `gemini-web` batch mode: one article can reuse a single Gemini Web client session for all missing images
    *   `gemini-web` runtime path: `/.gemini/wechat-director/gemini-web/`
*   **Output**:
    *   **Files**: `img/[Title]-cover-main.jpg` (Local retained).
    *   **Artifact**: `02_Draft.md` updated with image links.

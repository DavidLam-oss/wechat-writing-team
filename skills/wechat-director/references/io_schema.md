# WeChat Director I/O Schema

## 📁 输入规范 (Input)

1.  **Draft Article (`02_Draft.md`)**
    *   完整 Markdown 正文内容。
    *   或已归档的 `published/[Title].md`。
    *   用途：提取画面意境、IP 出现的场景。

## 📄 输出规范 (Output)

### 1. Storyboard (`Storyboard.md`)

*   **Path**: 与 `02_Draft.md` 同级（项目根目录）。
*   **Format**: Strict Markdown Structure (for script parsing).

```markdown
## Visual Storyboard

### Part A: 主视觉 cover-main (2.35:1)
(IP形象: 是)
(视觉模式: 默认电影感)
```
[中文 Prompt: 场景描述, IP特征...]
```

### Part B: 侧边栏 cover-sidebar (1:1)
(IP形象: 否)
(视觉模式: 默认电影感)
```
[中文 Prompt: 纯色背景 + 总结文字...]
```

### Part C: 内文配图 illustration
#### 插图 1: ...
(IP形象: 是)
(视觉模式: 默认电影感|认知草图)
```
[中文 Prompt: 动作描述...]
```
> Context: "原文上一段落的最后一句（用于定位插入点）"
```

### 2. 图片 (Images)

*   **Path**: 默认 `<项目>/zpicture.assets/`（可用 `--output-dir` 覆盖）。
*   **命名**: 封面 `cover-main.jpg` / `cover-sidebar.jpg`；内文配图 `[Title]-illustration-01.jpg`。
*   **规格**（单一来源 `scripts/image_validation.py`，尺寸取自 `director_core.ASPECT_RATIOS`）：

| 类型 | 尺寸 |
| :-- | :-- |
| cover-main | 1504 × 640 |
| cover-sidebar | 1024 × 1024 |
| illustration / quote | 768 × 1024（3:4） |

## 🛠️ 脚本契约 (`scripts/visualize.py`)

*   **Invoke**: Manual trigger by user or Agent.
*   **Input**:
    *   `--brief`: `Storyboard.md` (Must match Regex above).
    *   `--draft`: `02_Draft.md` (Required for Injection & Cleanup).
    *   `--workspace`: 文章工作区根（显式指定，规避自动检测歧义）。
    *   `--list-providers`: 只列出已配置渠道 JSON，不生成、不收费。
    *   `(视觉模式: ...)`: Optional planning metadata. Current script ignores this line; the selected lens must be reflected inside the Prompt text itself.
*   **Logic**:
    1.  **Parse**: Reads tasks and IP flags from Storyboard.
    2.  **Health Check**: When `gemini-web` is preferred, validates login state first; if unavailable in `auto` mode, skips to fallback providers.
    3.  **Generate**: Calls `gpt-image2` / `gemini`（按 `auto` 顺序回退），或显式指定的 `gemini-web`（injects IP ref if needed）。
    4.  **Compress**: Optimizes images via TinyPNG (if configured).
    5.  **Upload**: Puts illustrations to Tencent COS (if configured). Covers stay local.
    6.  **Inject**: Inserts COS URLs into `Draft.md` after the `Context` sentence.
    7.  **Retain**: 本项目**保留**本地原图（项目内原图由 writer `archive.py` 复制到 `published/zpicture.assets/`），不再删除。
*   **Provider Notes**:
    *   `--provider auto`: `gpt-image2` → `gemini`
    *   `--provider gemini-web`: 必须显式指定；需要技能目录下 `vendor/baoyu-danger-gemini-web` 与本机 `bun`
    *   `--gemini-web-login`: opens isolated Gemini Web login flow and exits
    *   `gemini-web` runtime path: `~/.gemini/wechat-director/gemini-web/`（可用 `api_keys.json` 的 `gemini_web.runtime_dir` 覆盖）
*   **Output**:
    *   **Files**: `zpicture.assets/cover-main.jpg`、`zpicture.assets/[Title]-illustration-01.jpg`（本地保留）。
    *   **Artifact**: `02_Draft.md` updated with image links.
*   **Exit Codes**: `0` = 全部任务产出成功；`1` = 运行期失败；`2` = 用法错误。

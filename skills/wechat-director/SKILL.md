---
name: wechat-director
version: 2.5.1
description: 视觉导演 Skill，负责为文章设计品牌一致的分镜与配图。包含默认电影感镜头与认知草图第二镜头，输出 Storyboard.md 并可调用绘图脚本。
triggers:
  - /draw
  - /visual
  - /配图
parameters:
  - name: input_file
    type: string
    required: true
    description: 文章草稿文件路径 (Draft) 或已归档文章路径
---
# 视觉导演系统 (WeChat Director)

**核心使命**: 为文章赋予**品牌一致的视觉叙事**。封面保持电影感，正文图可以在默认电影感镜头与认知草图第二镜头之间自动切换。

> **Tip**: 建议在 **归档前** (Stage 3) 运行本 Skill，默认将图片保存在项目 `zpicture.assets/` 目录。若在归档后运行，请务必指定 `--output-dir` 以免路径错误。

> **运行环境**：
> - 脚本需要 **Python 3.10+**；图片拼接与尺寸验收需要 **Pillow**。
> - `--brief` / `--draft` 等 CLI 路径相对**当前调用目录**；技能资源（`assets/`、`providers/`）以**技能自身目录**为基准解析，不使用机器绝对路径，macOS / Windows / Linux 通用。
> - 文章工作区根（`conductor/api_keys.json` 的基准）由 `scripts/workspace.py` 解析：**`--workspace` 显式 > `WECHAT_WORKSPACE` 环境变量 > 当前目录结构标记 > `--brief` 向上结构标记 > 报错**。定位不明时请显式传 `--workspace`。

## 🎭 核心角色: 张艺谋 (Visual Director)

*   **风格**: Flat Vector Illustration with Sticker Style (扁平矢量插画 + 贴纸风格)
*   **IP 形象**:
    *   **描述**: A bald Asian male (early 30s), wearing **signature bright red round-framed glasses**, neat goatee beard on chin. Character has **thick white outlines** around the entire silhouette (sticker style).
    *   **一致性**: 红色圆框眼镜、光头、山羊胡、白色描边必须保持一致。
    *   **参考图**: `assets/IP_Reference.png`（相对**技能根目录**；脚本以技能目录向上解析，技能被复制到任意位置仍正确，不使用机器绝对路径）。

## 🎥 双镜头系统 (Visual Lenses)

### 1. 默认电影感镜头 (Default Cinematic)

*   **适用**: 主视觉封面、个人故事、情绪转折、复盘感悟、需要氛围与场景的段落。
*   **气质**: 电影构图、温暖技术感、扁平矢量贴纸、场景化叙事。
*   **规则**: Part A 主视觉与 Part B 侧边栏默认使用本镜头，保持读者熟悉的品牌门面。

### 2. 认知草图第二镜头 (Cognitive Sketch)

*   **适用**: 教程、方法论、插件介绍、工作流、常见坑、判断标准、抽象概念解释。
*   **气质**: 原风格内的白板解释视角，而不是换画师。保留红眼镜 IP、扁平插画、白色贴纸描边和 3:4 正文尺寸。
*   **画法**: 一张图只讲一个核心动作或结构。少背景、少道具、短中文标注，用一个低科技隐喻解释复杂概念。
*   **IP 要求**: IP 必须承担核心动作，例如拉线、分拣、修补、搭桥、称重、守门、拆包、把内容塞进一个怪装置；不能只是站在角落里摆 pose。
*   **禁止**: 不要切换成其它 IP、黑色小怪物、纯手绘线稿或 PPT 信息图。

### 自动判断与手动覆盖

*   **默认策略**: 自动判断正文图镜头。封面保持默认电影感，正文图根据文章内容选择。
*   **优先认知草图**: 安装/配置/排错/步骤教程、功能解释、流程闭环、常见坑、方法分层、抽象概念可视化。
*   **优先默认电影感**: 人物情绪、生活场景、故事推进、感悟复盘、需要氛围留白的段落。
*   **手动覆盖**: 若用户指定"正文图用认知草图模式"、"保持默认视觉"、"插图 2 和 3 用认知草图"，必须优先服从用户指定。

## 🚀 工作流程

### Step 1: 分镜设计 (Storyboard)

阅读输入文章，根据**文章篇幅**、**情绪节奏**与**认知锚点**，设计**适量**的插图位置，并为每张图判断视觉镜头。

*   **数量原则**: **跟随情绪，不设限**。不要刻意计算字数。在每个需要"视觉呼吸"的**留白处**或**情绪转折点** (Emotional Twist) 插入。对于 1500-2000 字的文章，通常 4-6 张为宜。
*   **核心目标**: 用画面去承接文字无法表达的留白；教程/方法论内容则优先把关键判断、流程、状态或隐喻画成一个清晰动作。

**输出交付物**: `Storyboard.md`。

> ⚠️ **重要**: 输出格式必须严格遵循 `references/io_schema.md` 中定义的 Markdown 结构与 Regex 规则。

**设计要求**:
1.  **IP 标记**: 每个 Code Block 前必须根据内容判断是否需要 IP 形象 (`(IP形象: 是/否)`)。
    *   **重要**: 若标记为 `(IP形象: 是)`，则生成的 Prompt **必须包含**上方定义的完整 IP 形象描述 (A bald Asian male...)。
2.  **视觉模式标记**: Part C 每张内文配图建议在 IP 标记后增加 `(视觉模式: 默认电影感)` 或 `(视觉模式: 认知草图)`。
    *   **自动判断**: 未手动指定时，根据文章类型与段落内容自动选择。
    *   **品牌一致性**: 认知草图仍必须保留红眼镜 IP 与扁平贴纸体系，不得换成其它角色或完全不同画风。
3.  **尺寸规范 (Aspect Ratio)**:
    *   **Part A (主视觉)**: 必须在开头标明 `movie composition, 2.35:1 aspect ratio`，并在结尾使用 `--ar 2.35:1`。**禁止提供 Context 字段** (No Context needed)。
    *   **Part B (侧边栏)**: 纯色背景 (需提取主视觉主色)，必须标明 `1:1 aspect ratio`。**禁止提供 Context 字段** (No Context needed)。
    *   **Part C (配图)**: 必须在开头标明 `portrait composition, 3:4 aspect ratio`。这是手机阅读最佳比例。
    *   **Context (锚点)**: 每一张**内文配图 (Part C)** 都必须提供 `Context` 字段。
        *   **定义**: 该图片应插入位置的**上一段落的最后一句话**。
        *   **要求**: 必须是原文中的原句，确保唯一性。
        *   **格式**: `> Context: "原文句子..."`

4.  **侧边栏内容 (Part B)**: 纯色背景 + **必须使用中文** (Must use Chinese characters)。
    *   **字数限制**: 总共 **4-6个汉字**的核心短语 (e.g., "AI编程 / 一次过")。
    *   **排版**: 必须按语义拆分为 **上下两行** 进行排版 (Split into two lines)。
    *   **禁止**: 绝对禁止出现英文单词 (No English allowed)。

### Step 2: 出图前决策 (Check) —— 强制确认，不可跳过

**禁止**因为"只有一个可用 provider"就自动选默认值。每次运行 `/draw` 都必须重新读取 `conductor/api_keys.json` 并重新向用户展示渠道列表，等待用户显式选择后再执行。

**流程**：
1. 运行 `scripts/config_check.py` 或 `scripts/visualize.py --list-providers` 展示当前可用渠道（只读，不生成、不收费）。
2. 向用户展示选项与影响，等待选择：
   - 当前 Agent / 平台内置生图工具
   - 已保存的第三方 API（来自 `conductor/api_keys.json`）
   - 输入新的第三方 API（只需 provider / base_url / model / api_key）
   - 手动填入图片 URL
3. 用户确认"立即生成 / 只保留分镜 / 暂不执行"后再进入 Step 3。

新增 API 建议先核对官方文档；能力不明确时，先询问是否进行可能收费的最小生成测试。

### Step 3: 执行 (Execution) - Optional

调用 `scripts/visualize.py` 脚本批量生成图片。

*   **全流程自动化**: 推荐同时传入 `--draft` 参数，脚本将自动完成 "生成 -> 压缩 -> 上传COS -> 插入正文" 的完整闭环。
*   **纯上传模式 (`--upload-only`)**: 当配图已通过原生生图能力（如 Antigravity / 本地生成）生成完毕并存放在 `zpicture.assets/` 时，传入 `--upload-only` 可跳过 API 生图，直接复用本地图执行压缩、上传腾讯云 COS 并自动将 COS 在线链接注入正文。
*   **Provider 选择**: `--provider` 可选 `auto`（默认）/ `gemini-web` / `gemini` / `gpt-image2`。
    `auto` 的候选顺序固定为 **`gpt-image2` → `gemini`**，逐个尝试、失败自动回退。
    vendored **`gemini-web` 不会进入 `auto`**，必须显式 `--provider gemini-web` 才会使用。
*   **gemini-web 前置条件**: 需要技能目录下的 `vendor/baoyu-danger-gemini-web` 与本机 `bun`，缺任一项会在运行时明确报错。它按图逐次调用，**没有「单次会话批量生图」**。
*   **SiliconFlow**: `providers/siliconflow.py` 仍存在，但当前**没有任何路径能选中它**（不在 `--provider` 候选，也不在 `auto` 解析里）。
*   **退出码**: `0` = 全部任务产出成功；`1` = 运行期失败（配置/文件/无任务/有任务未产出）；`2` = 用法错误。
*   **首次登录**: 首次使用 `gemini-web` 前，先运行 `python3 skills/wechat-director/scripts/visualize.py --gemini-web-login` 完成独立登录初始化。
*   **隔离原则**: `gemini-web` 默认使用**用户主目录**下 `.gemini/wechat-director/gemini-web/` 的独立 runtime，不复用日常 Chrome Profile（可用 `api_keys.json` 的 `gemini_web.runtime_dir` 覆盖）。
*   **IP 增强**: 脚本会自动识别 Storyboard 中的 `(IP形象: 是)` 标记。若启用，将自动读取技能目录下 `assets/IP_Reference.png` 作为 Gemini Web / Gemini API 的参考图输入。

### Step 4: 图片交付验收（Agent / 平台出图时必做）

若图片不是由 `visualize.py` 生成（例如用当前 Agent 或平台工具出图），在注入正文、交给 writer 发布之前，先跑一次验收：

```bash
python3 skills/wechat-director/scripts/validate_images.py <项目>/zpicture.assets --brief <项目>/Storyboard.md
```

对照分镜确认齐图，并检查尺寸 / 比例 / 可读性（缺图、图片损坏、尺寸不足、比例错误、缺少 Pillow 都会失败）。验收通过后再注入正文。

## 🛠️ 脚本工具箱

> 2026-10-05 按职责拆分：`visualize.py` 由 1127 行降为 534 行，
> 其余按「基础设施 / 解析 / 桥接 / 生图适配器」分模块。
> **调用方式完全不变**（仍是从 `scripts/visualize.py` 进入）；
> `tests/` 中的表征测试在拆分前后逐条比对行为（现有 **32 条**）。
> 同日另修：补齐 `gemini-web` 分发分支、退出码改为「非 0 表示有任务未产出」。
> 2026-10-06：工作区解析改为跨平台结构标记（`scripts/workspace.py`），
> 新增 `--workspace` / `--list-providers`，输出目录统一为 `zpicture.assets/`。

| 脚本 | 功能 | I/O 规范 |
|:---|:---|:---|
| `scripts/visualize.py` | **CLI 入口** + 编排（`VisualPipeline`：生图/压缩/上传/注入） | 读取 `Storyboard.md` 中的 Prompt 代码块 |
| `scripts/director_core.py` | 基础设施：日志、常量表、路径解析、配置加载、文本工具 | 被其他模块 import；无兄弟依赖 |
| `scripts/brief_parser.py` | Storyboard 解析器（含 Context 提取） | 输入 `Storyboard.md` → `(title, tasks)` |
| `scripts/obsidian_bridge.py` | Obsidian CLI 桥接（写属性 / 打开预览） | 需要本机 `obsidian` CLI |
| `scripts/workspace.py` | 工作区根解析（显式 > 环境变量 > 结构标记） | 被同目录脚本 import |
| `scripts/config_check.py` | 环境与渠道检测（Python / Pillow / Obsidian CLI / 已配置 provider） | 只读，不生成、不收费 |
| `scripts/validate_images.py` | Agent/平台生图后的独立齐图与规格验收 | `image_validation.py` 为规格单一来源 |
| `scripts/image_validation.py` | 图片交付规格（尺寸取自 `director_core.ASPECT_RATIOS`） | 被 `validate_images.py` import |
| `scripts/providers/gemini.py` | Gemini 生图适配器（API 与 Web 两条通道） | — |
| `scripts/providers/gpt_image2.py` | GPT-Image-2 生图适配器 | — |
| `scripts/providers/siliconflow.py` | SiliconFlow 生图适配器（⚠️ **当前未接入任何选中路径**） | — |
| `tests/test_visualize.py` | 行为护栏（32 条：纯函数 / 解析快照 / 编排 / CLI 退出码 / IP 路径） | `cd tests && python3 -m unittest test_visualize` |

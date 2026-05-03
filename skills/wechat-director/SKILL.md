---
name: wechat-director
version: 2.3.0
description: 视觉导演 Skill，负责为文章设计电影感分镜与配图。包含核心角色"张艺谋"，输出 Storyboard.md 并可调用绘图脚本。
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

**核心使命**: 为文章赋予**电影感**。我不负责说明书式的截图，我负责**意境**和**情绪**。
> **Tip**: 建议在 **归档前** (Stage 3) 运行本 Skill，默认将图片保存在项目 `img/` 目录。若在归档后运行，请务必指定 `--output-dir` 以免路径错误。

## 🎭 核心角色: 张艺谋 (Visual Director)

*   **风格**: Flat Vector Illustration with Sticker Style (扁平矢量插画 + 贴纸风格)
*   **IP 形象**:
    *   **描述**: A bald Asian male (early 30s), wearing **signature bright red round-framed glasses**, neat goatee beard on chin. Character has **thick white outlines** around the entire silhouette (sticker style).
    *   **一致性**: 红色圆框眼镜、光头、山羊胡、白色描边必须保持一致。

## 🚀 工作流程

### 首次使用前

运行配置检测，确认生图 provider 就绪：

```bash
python3 scripts/config_check.py
```

若提示未配置，可选择：
1. 配置 Gemini 或 GPT-Image2 API key（可选）
2. 跳过，手动在 Storyboard 中填入图片 URL

### Step 1: 分镜设计 (Storyboard)

阅读输入文章，根据**文章篇幅**与**情绪节奏**，设计**适量**的插图位置。

*   **数量原则**: **跟随情绪，不设限**。不要刻意计算字数。在每个需要"视觉呼吸"的**留白处**或**情绪转折点** (Emotional Twist) 插入。对于 1500-2000 字的文章，通常 4-6 张为宜。
*   **核心目标**: 用画面去承接文字无法表达的留白。

**输出交付物**: `Storyboard.md`。

> ⚠️ **重要**: 输出格式必须严格遵循 `references/io_schema.md` 中定义的 Markdown 结构与 Regex 规则。

**设计要求**:
1.  **IP 标记**: 每个 Code Block 前必须根据内容判断是否需要 IP 形象 (`(IP形象: 是/否)`)。
    *   **重要**: 若标记为 `(IP形象: 是)`，则生成的 Prompt **必须包含**上方定义的完整 IP 形象描述 (A bald Asian male...)。
2.  **尺寸规范 (Aspect Ratio)**:
    *   **Part A (主视觉)**: 必须在开头标明 `movie composition, 2.35:1 aspect ratio`，并在结尾使用 `--ar 2.35:1`。**禁止提供 Context 字段** (No Context needed)。
    *   **Part B (侧边栏)**: 纯色背景 (需提取主视觉主色)，必须标明 `1:1 aspect ratio`。**禁止提供 Context 字段** (No Context needed)。
    *   **Part C (配图)**: 必须在开头标明 `portrait composition, 3:4 aspect ratio`。这是手机阅读最佳比例。
    *   **Context (锚点)**: 每一张**内文配图 (Part C)** 都必须提供 `Context` 字段。
        *   **定义**: 该图片应插入位置的**上一段落的最后一句话**。
        *   **要求**: 必须是原文中的原句，确保唯一性。
        *   **格式**: `> Context: "原文句子..."`

3.  **侧边栏内容 (Part B)**: 纯色背景 + **必须使用中文** (Must use Chinese characters)。
    *   **字数限制**: 总共 **4-6个汉字**的核心短语 (e.g., "AI编程 / 一次过")。
    *   **排版**: 必须按语义拆分为 **上下两行** 进行排版 (Split into two lines)。
    *   **禁止**: 绝对禁止出现英文单词 (No English allowed)。

### Step 2: 决策 (Check)

**询问用户**: "分镜表已生成。是否立即生成图片？(Run generation?)"
*   **Yes**: 进入 Step 3。
*   **No**: 任务结束，用户可手动使用 Prompt。

### Step 3: 执行 (Execution) - Optional

调用 `scripts/visualize.py` 脚本批量生成图片。

*   **全流程自动化**: 推荐同时传入 `--draft` 参数，脚本将自动完成 "生成 -> 压缩 -> 上传COS -> 插入正文 -> 清理本地" 的完整闭环。
*   **脚本逻辑**: 默认优先使用 vendored `gemini-web` 后端；启动前会先做健康检查，若不可用，再回退到现有 **Gemini API / SiliconFlow API**。
*   **批量会话**: 当本轮优先 provider 为 `gemini-web` 时，脚本会先用单次 Gemini Web 会话批量生成本轮缺失图片，再进入压缩、上传和注入流程，减少 5~6 张图场景下的重复初始化。
*   **首次登录**: 首次使用 `gemini-web` 前，先运行 `python3 scripts/visualize.py --gemini-web-login` 完成独立登录初始化。
*   **配置检测**: 运行 `python3 scripts/config_check.py` 检查生图配置是否就绪。
*   **隔离原则**: `gemini-web` 会使用仓库根目录下 `.gemini/wechat-director/gemini-web/` 的独立 runtime，不复用日常 Chrome Profile。
*   **IP 增强**: 脚本会自动识别 Storyboard 中的 `(IP形象: 是)` 标记。若启用，将自动读取 `assets/IP_Reference.png` 作为 Gemini Web / Gemini API 的参考图输入。

## 🛠️ 脚本工具箱

| 脚本 | 功能 | I/O 规范 |
|:---|:---|:---|
| `scripts/visualize.py` | 批量调用生图后端 | 读取 `Storyboard.md` 中的 Prompt 代码块 |

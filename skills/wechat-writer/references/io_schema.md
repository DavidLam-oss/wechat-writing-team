# WeChat Writer I/O Schema

## 📁 目录规范

**项目根目录**: `articles/Project_[Title]/`

**项目级 Seed 目录**: `articles/Project_[Title]/_source/Seeds/`

**长期 Seed 目录**: `knowledge/seeds/`

## 📄 核心交付物 (Artifacts)

| 阶段           | 文件名                    | 描述                                                                                              | Checkpoint        |
| :----------- | :--------------------- | :---------------------------------------------------------------------------------------------- | :---------------- |
| **Step 0.5** | `Seed_[Topic].md`      | **发芽种子**。<br>包含：当前外部素材的结构化洞察、案例、反方视角、第一性问题，以及与 David 现有素材的连接点。<br>用途：补视角、补案例、补问题意识。 | 审核是否值得吸收进策划 |
| **Step 1**   | `01_Plan.md`           | **策划案**。<br>包含：从 `Cleaned_*.md` 吸收的素材摘要、`选题质检卡`、`人机边界卡`、从 `Seed_*.md` 吸收的外部案例/反方视角/第一性问题、文章结构大纲、主线回扣设计、`Research_Report.md` 中的事实核查表，以及固定区块 `SEO 决策卡`。<br>用途：确保方向正确、事实无误，并作为 Stage 2 / Stage 3 唯一允许消费的 SEO 输入源。 | 审核大纲结构<br>审核事实来源  |
| **Step 1.5** | `SEO_Report.md`         | **SEO 关键词报告**（Stage 1 中间产物）。<br>包含：种子词、候选词（指数/趋势/适合位置）、新词更新到积累库的记录，以及本轮 `采用 / weak-signal / skip SEO化` 的原始判断依据。<br>用途：留存调研证据；下游不得绕过 `01_Plan.md` 直接消费本文件。 |
| **Step 2**   | `02_Draft.md`          | **正文稿**。<br>包含：完整文章正文，并按 `01_Plan.md` 的 `SEO 决策卡` 自然吸收关键词约束。<br>*注：批评意见和修改指令可作为批注附在文末。*<br>用途：内容质量验收。                                 | 审核文章内容<br>检查 AI 味 |
| **Step 2.5** | `Directive_*.md`       | **综改指令**。<br>包含：主编针对初稿的修改指令。<br>用途：指导主笔进行修改。                                                    | 确认修改方向            |
| **Step 3**   | `03_Production.md`     | **制作包**。<br>包含：<br>- 4个候选标题<br>- 摘要 (Excerpt)<br>- Tags<br>并基于 `01_Plan.md` 的 `SEO 决策卡` 完成包装。<br>用途：发布前的包装准备。                         | 选定标题              |
| **Step 4**   | `published/[Title].md` | **发布稿**。<br>包含：Frontmatter + 最终正文；正文图片已完成 SEO 显示名检查，并保留 Obsidian 图片尺寸参数。个人网站生成时再清理 alt 中的尺寸参数。                                                            | 确认归档成功            |

## 📝 草稿元数据标准 (Draft Header)

`02_Draft.md` 文件头部通常包含以下元信息引用块，用于流转追踪。**归档时将由 `archive.py` 自动根据关键词清洗**。

> **版本**: v1.0
> **主笔**: [Persona Name]
> **创建时间**: YYYY-MM-DD

---

*注意：`archive.py` 仅在检测到上述关键词时才会执行头部清洗，避免误删正文引言。*

## 🧭 `01_Plan.md` 必填区块

`01_Plan.md` 必须包含 `选题质检卡`、`人机边界卡` 与 `SEO 决策卡`。
推荐结构如下：

```markdown
## 选题质检卡

- 好奇感: 强 | 中 | 弱
- 具体钩子: ...
- 信息增量: 强 | 中 | 弱
- 新增价值: ...
- 共鸣感: 强 | 中 | 弱
- 对应读者处境: ...
- 结论: 继续 | 补素材 | 调整角度

## 人机边界卡

- David 原话与亲历: ...
- AI 可辅助: ...
- 禁止虚构: ...
```

为防止 SEO 结果停留在中间产物，`SEO 决策卡` 供 Stage 2 与 Stage 3
统一消费。推荐结构：

```markdown
## SEO 决策卡

- 状态: 采用 | weak-signal | skip SEO化
- 标题主词: ...
- 正文/摘要辅助词: ...
- Tags 候选: ...
- 放置计划: 标题 / 摘要 / 开头段 / Tags
- 禁用或降级词: ...
- 备注: 查无结果 / 仅下降词 / 主题不适合 SEO 化时的原因
```

约束：
- Stage 2 / Stage 3 只允许从这里读取 SEO 约束，不直接读取 `SEO_Report.md`
- 若状态为 `skip SEO化`，标题、摘要、正文均不得为了完成流程硬塞关键词
- 若状态为 `weak-signal`，可轻量吸收稳定相关词，但不强制标题承载
- `选题质检卡` 若结论为 `补素材` 或 `调整角度`，不得直接进入 Stage 2
- `人机边界卡` 中列为 `禁止虚构` 的内容，不得出现在正文里

## 🧩 `01_Plan.md` 示例样本

若需要参考常见章节顺序与颗粒度，可查看
`references/template_01_plan.md`。

说明：
- 这是**半空白示例样本**，用于帮助 AI 或人工起草 `01_Plan.md`
- 它**不是强制模板**，章节顺序、详略和命名都可按题目调整
- 其中 `Seed 使用情况` 为推荐区块，不是硬性必填；但当本篇未启用
  `/sprout` 时，建议用一句话说明原因

## 🏷️ Frontmatter 标准 (Step 3/4)

在完成文章撰写后，在文章最顶部生成 YAML Frontmatter，用于公众号排版与个人博客主页同步：

```yaml
---
title: "文章标题"
date: "YYYY-MM-DD"
slug: "english-slug-for-url"
excerpt: "50-100字的文章核心摘要，用于博客列表页展示与微信后台抓取"
cover: "zpicture.assets/cover-combined.jpg"
tags: [Obsidian, 知识管理, 自动化]
obsidianSection: "publishing"   # 可选：Obsidian 专题页阶段归类
status: published
---
```

### 博客文章 Frontmatter 生成规则

1. **必含字段**:
   - `title`: 文章标题（若是 Obsidian 系统教程，使用 `Obsidian 入门XX：文章标题` 格式，`入门` 与数字中间无空格）。
   - `date`: 发布日期，格式 `YYYY-MM-DD`。
   - `slug`: 英文短链，用于个人主页 URL。
   - `excerpt`: **50-100 字**的文章核心摘要（兼顾个人主页列表页展示与微信后台限制，微信硬上限 120 字）。
   - `tags`: 必须从 36 个官方白名单中挑选 2-4 个，严禁自行创造标签。
   - `cover`: 封面路径（可选，脚本匹配 `cover-combined` 或 `cover-main`，若无则留空）。
   - `status`: published

2. **🏷️ Tags 36 个官方白名单（必须挑选 2-4 个，严禁自行创造标签）**:
   - **知识管理类 (6个)**: `Obsidian`, `Obsidian入门`, `知识管理`, `Obsidian插件`, `笔记同步`, `Web剪藏`
   - **AI与智能体 (8个)**: `AI Agent`, `AI模型`, `Claude Code`, `Codex`, `WorkBuddy`, `OpenClaw`, `提示词工程`, `MCP`
   - **效率与工具 (7个)**: `效率工具`, `自动化`, `苹果生态`, `终端命令行`, `Raycast`, `Typeless`, `任务管理`
   - **编程与开源 (3个)**: `编程开发`, `AI编程`, `开源`
   - **创作与发布 (5个)**: `内容创作`, `微信公众号`, `WeChat Converter`, `多平台分发`, `排版与导出`
   - **运维与建站 (2个)**: `服务器运维`, `SEO与数据分析`
   - **个人与思考 (5个)**: `生活随笔`, `个人成长`, `职场思考`, `复盘与踩坑`, `副业与出海`

3. **🏷️ Obsidian 专题页 Frontmatter 规则**:
   主站 `/blog/obsidian` 会自动从博客文章收录 Obsidian 相关内容，依赖 Frontmatter 三层规则：
   - **tags 必含 `Obsidian`**: 如果当前文章是 Obsidian 相关内容，tags 中必须包含 `Obsidian`（至少进入专题页「Obsidian 延伸阅读」）。
   - **系统教程编号格式**: 标题为 `Obsidian 入门数字：标题`（`入门` 与数字间无空格）→ 进入主学习路径。仅系统教程系列使用；随笔/插件体验/工具推荐等非编号文章不得强行编号。
   - **`obsidianSection` 字段（可选）**: 若文章适合按学习路径收录到 Obsidian 专题教程中，请额外添加 `obsidianSection` 字段，取值范围必须为以下 8 个之一：

| 值 | 阶段 | 涵盖范围与说明 |
| --- | --- | --- |
| `first-steps` | 新手起步 | 安装、Vault、界面、第一篇笔记、Markdown 入门 |
| `basics` | 笔记基础 | 双链、标签、属性、搜索、附件 |
| `plugins-automation` | 插件、模板与自动化 | Templater、Dataview TODO、QuickAdd、Commander 等 |
| `advanced-organization` | 高级组织 | Dataview、Canvas、数据库、Dashboard、知识库结构 |
| `ai-workflow` | AI + Obsidian 工作流 | Claude Code、Gemini CLI、Agent、MCP、Skill、Terminal |
| `collecting` | 内容收集与剪藏 | Web Clipper、飞书/B站/公众号剪藏、微信读书、Flomo |
| `sync-backup` | 同步、备份与图片管理 | iCloud、坚果云、SyncThing、COS、图床 |
| `publishing` | 发布、导出与内容分发 | 公众号/知乎/小红书、Word/PDF、发布助手、WeChat Converter |

**归档透传与校验**: `archive.py` 支持将 `obsidianSection` 透传到 published 稿，并在归档时自动校验 36 个 Tags 白名单、Tags 数量 (2-4个)、50-100 字摘要以及 `obsidianSection` 的合法性。

**⚠️ 格式要求**: Frontmatter `---` 结束后直接接正文第一段，不要空行，不要一级标题。

## 🖼️ 发布前图片 SEO 规范 (Step 4)

归档前必须做一次图片巡检，避免个人网站把截图默认名、随机文件名当成图片
alt。`|400` 这类 Obsidian 显示参数不在归档时删除，应留给个人网站生成层
单独处理。

流程：
- 先读取 `02_Draft.md`、`03_Production.md`，以及 `01_Plan.md` 的
  `SEO 决策卡`
- 扫描正文图片语法：`![...](...)` 与 `![[...]]`
- 若正文没有任何图片，暂停并提醒用户是否等插图完成后再归档
- 若已有图片，模型根据图片所在小节、前后段落、最终标题、摘要、Tags
  和已批准 SEO 关键词，为每张图生成自然的显示名/alt
- 归档稿中保留 Obsidian 尺寸参数，例如 `![描述|400](url)`；只修改
  `|400` 前面的描述，不改 URL
- 个人网站生成时应把 `![描述|400](url)` 转成干净 alt（`描述`），并由
  网站 CSS 或图片组件控制展示尺寸

命名约束：
- 名称必须具体、可读，能说明画面或段落作用
- 可自然吸收 1 个贴切 SEO 关键词，但禁止关键词堆砌
- 避免 `Pasted image`、`Screenshot`、`IMG_`、`Gemini_`、随机哈希等
  无意义名称
- `archive.py` 只做发布归档，不负责语义命名或删除图片尺寸；语义命名必须在
  调用脚本前由模型完成

## 📝 临时文件规范

脚本输入的 JSON 文件统一放在项目目录下：
- 命名格式：`_temp_{script_name}.json`
- 示例：`articles/Project_测试/_temp_cleaner.json`
- 脚本执行后可保留或删除（推荐保留用于调试）

## 🌱 Seed 文件规范

`Seed_[Topic].md` 使用以下结构：

推荐以 `references/template_seed.md` 作为起草样例，再按当前主题改写。

```markdown
# Seed: [Topic]

> **生成时间**: YYYY-MM-DD
> **素材类型**: person | event | story
> **来源**: 用户提供 / 搜索补充 / 素材库
> **状态**: project | canonical

## 1. 一句话洞察

## 2. 核心对象

## 3. 事实与来源

## 4. 外部案例

## 5. 反方视角

## 6. 第一性问题

## 7. 可嫁接到 David 经验的点

## 8. 可写方向

## 9. 相关旧文
```

约束：
- `Seed` 只接受 `person / event / story`，不接受纯 `concept / trend`（`trend` 需先按 `routine_sprout.md` 的「热点嫁接四问」降级为 `event` / `story`）
- 每个 Seed 至少包含 `1` 个具体人物或事件抓手
- 若使用搜索补充，必须附来源链接
- `可嫁接到 David 经验的点` 只能提示连接，不能虚构 David 未经历的事实

## 🛠️ 脚本 I/O 契约 (Script Contracts)

为确保 AI Agent 正确调用脚本，请遵循以下 JSON 格式。

### 0. Seed (`/sprout`, Non-Script Artifact)
*   **Input**: 用户素材、外部链接、搜索结果或 `knowledge/素材库.md` 中的条目
*   **Binding Rule**:
    - 若当前已在某个 `Project_[Title]` 上下文中，默认写入该项目
    - 若独立触发 `/sprout` 或 `/harvest`，必须提供 `project` 参数，或使用 `title` 作为目标项目标题
    - 若目标项目不存在，先创建 `articles/Project_[Title]/` 与 `_source/Seeds/`
    - 默认不允许无项目归属的 projectless Seed
*   **Output**:
    1. 项目级 Seed: `articles/Project_[Title]/_source/Seeds/Seed_[Topic].md`
    2. 长期 Seed: `knowledge/seeds/Seed_[Topic].md`
*   **Promotion Rule**:
    - 默认先写项目级 Seed
    - 只有满足“后续可复用”的条目才晋升为长期 Seed

### 1. Cleaner (`scripts/cleaner.py`)
*   **Input**: JSON File
    ```json
    {
      "source_file": "/abs/path/to/raw_material.txt",
      "cleaned_content": "Markdown Content..."
    }
    ```
*   **Output**: `[Project_Dir]/Cleaned_[Name].md`

### 2. Research (`scripts/research.py`)
*   **Input**: JSON File
    ```json
    {
      "data": {
        "fact_checks": [
          { "claim": "...", "verdict": "Verified", "truth": "...", "source": "..." }
        ]
      }
    }
    ```
*   **Output**: `[Directory]/Research_Report.md`

### 3. Review (`scripts/review_toolkit.py`)

**Mode: Critique**
*   **Input**: JSON File
    ```json
    {
      "source_file": "path/to/02_Draft.md",
      "critic_persona": "罗永浩",
      "meta": {
        "score": 85,
        "verdict": "Pass"  // Pass, Needs Work, Fail
      },
      "overall_comment": "整体评价...",
      "critique_points": {
        "logic_flaws": [
          { "point": "逻辑不通...", "severity": "High" }
        ],
        "ai_smell": {
            "score": 90,
            "evidence": ["滥用'综上所述'", "缺乏细节"]
        },
        "content_depth": {
            "status": "Needs Work",
            "score": 75,
            "evidence": ["第二节观点缺少具体场景支撑"],
            "priorities": ["补一个来自原始素材的真实动作"]
        },
        "david_layer": {
            "status": "Pass",
            "score": 88,
            "evidence": ["整体像第一人称分享，没有营销腔"],
            "priorities": []
        }
      }
    }
    ```
*   **Output**: `[Critique_Report]*.md`

**Mode: Directive**
*   **Input**: JSON File
    ```json
    {
      "title": "Article Title",
      "status": "PENDING",
      "conflict_resolution": { "has_conflict": false, "details": "" },
      "critique_summary": [
          { "source": "罗永浩", "point": "逻辑漏洞", "action": "修改第三段" }
      ],
      "editorial_suggestions": [
        { "original": "...", "suggestion": "..." }
      ]
    }
    ```
*   **Output**: `Directive_*.md`

**Mode: Feedback**
*   **Input**: JSON File
    ```json
    {
      "overall_verdict": "Pass",
      "best_quote": "...",
      "tests": {
        "click_test": { "decision": "Yes", "reason": "..." },
        "finish_test": { "decision": "Yes", "drop_point": "..." }
      }
    }
    ```
*   **Output**: `[User_Feedback]*.md`

### 4. Archive (`scripts/archive.py`)
*   **Input**: JSON File
    ```json
    {
      "source_file": "path/to/02_Draft.md", 
      "frontmatter": {
        "title": "Obsidian 入门82：实战指南",
        "date": "2026-10-03",
        "slug": "obsidian-guide-82",
        "tags": ["Obsidian", "知识管理", "效率工具"],
        "excerpt": "本文详细介绍 Obsidian 核心技巧与自动化配置，助你打造高效个人知识库体系。",
        "cover": "zpicture.assets/cover-combined.jpg",
        "obsidianSection": "plugins-automation"
      }
    }
    ```
*   **Output**: 
    1. `published/[Title].md` (Final Article)
    2. Project retained in `articles/Project_[Title]/` (不再移动到 `conductor/archive/`)
    3. Project `zpicture.assets/` 合并复制到 `published/zpicture.assets/`（原图保留在项目内）
    4. If `frontmatter.cover` is empty, auto-pick from `published/zpicture.assets` by:
       `cover-combined` > `cover-main` (no other fallback)

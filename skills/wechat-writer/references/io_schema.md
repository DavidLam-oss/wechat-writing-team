# WeChat Writer I/O Schema

## 📁 目录规范

**项目根目录**: `To-be-used/Project_[Title]/`

**项目级 Seed 目录**: `To-be-used/Project_[Title]/_source/Seeds/`

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
| **Step 4**   | `published/[Title].md` | **发布稿**。<br>包含：Frontmatter + 最终正文。                                                            | 确认归档成功            |

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

## 🏷️ Frontmatter 标准 (Step 4)

```yaml
---
title: "文章标题"
date: "YYYY-MM-DD"
slug: "english-slug-for-url"
excerpt: "一句话摘要，用于列表页展示"
cover: "Wechat/published/img/cover-combined.jpg"
tags: [Tag1, Tag2]
status: published
---
```

`cover` 仅用于公众号封面，脚本只会自动匹配 `cover-combined` 或
`cover-main`。若不存在则留空。`excerpt` 需在 Stage 3 控制为：建议 `<=45` 字，硬上限 `<=120` 字。

**⚠️ 格式要求**: Frontmatter `---` 结束后直接接正文第一段，不要空行，不要一级标题。

## 📝 临时文件规范

脚本输入的 JSON 文件统一放在项目目录下：
- 命名格式：`_temp_{script_name}.json`
- 示例：`To-be-used/Project_测试/_temp_cleaner.json`
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
- `Seed` 只接受 `person / event / story`，不接受纯 `concept / trend`
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
    - 若目标项目不存在，先创建 `To-be-used/Project_[Title]/` 与 `_source/Seeds/`
    - 默认不允许无项目归属的 projectless Seed
*   **Output**:
    1. 项目级 Seed: `To-be-used/Project_[Title]/_source/Seeds/Seed_[Topic].md`
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
        "title": "Final Title",
        "slug": "url-slug",
        "tags": ["tag1"],
        "excerpt": "Summary...",
        "cover": "Wechat/published/img/cover-combined.jpg"
      }
    }
    ```
*   **Output**: 
    1. `published/[Title].md` (Final Article)
    2. Moved Project to `conductor/archive/YYYYMMDD_[Title]/`
    3. Move project `img/` to fixed path `published/img` (old one backed up as `img_prev_*`)
    4. If `frontmatter.cover` is empty, auto-pick from `published/img` by:
       `cover-combined` > `cover-main` (no other fallback)

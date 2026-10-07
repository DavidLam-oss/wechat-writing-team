---
name: wechat-writer
version: 3.7.0
description: 微信公众号写作全流程 Skill (v3.7.0)，整合从选题定位到剪藏找料、素材发芽、再到归档的完整工作流。以「账号定位卡」（knowledge/account_positioning.md：4 条内容支柱 + 「个人与思考」标签组）作为选题与素材分拣的判据来源；Stage 1 内置「剪藏找料」从剪藏库（knowledge/_inbox/）按内容支柱为当前选题取外部素材；/sprout 的 trend 通道由「一律拦截」改为「归属检查 + 热点嫁接四问」有条件放行。归档脚本完全采用 Python 标准库操作，支持 SEO 关键词调研嵌入、博客与公众号 Frontmatter 规范（包含 50-100 字摘要、36 个官方白名单 Tags 挑选 2-4 个、Obsidian 专题页 frontmatter 归类及 obsidianSection 归档透传）、归档前图片 SEO 巡检，并包含 David 版选题质检、人机边界卡、主线回扣与 L3/L4 审校。支持 /interview（访谈挖掘）、/write（素材转化）、/sprout（外部素材发芽）和 /harvest（批量发芽）。当用户素材视角单一、只有感想没有人物/事件/案例支撑时，必须先绑定或创建目标项目，再使用 Seed 流程补素材，然后进入正文写作。
triggers:
  - /write
  - /写作
  - /interview
  - /访谈
  - /sprout
  - /发芽
  - /harvest
  - /收获
parameters:
  - name: title
    type: string
    required: false
    description: 文章标题（/write 模式必填）；也可在 /sprout 或 /harvest 独立触发时，作为目标项目标题使用
  - name: topic
    type: string
    required: false
    description: 访谈话题（/interview 模式必填）
  - name: project
    type: string
    required: false
    description: 目标项目标题（/sprout 和 /harvest 独立触发时推荐填写；若项目不存在则自动创建 `Project_[Title]`）
  - name: from-stage
    type: integer
    default: 0
    description: 从第几阶段开始执行 (0:Interview, 1:Plan, 2:Draft, 3:Production, 4:Archive)
---
# 微信公众号写作系统 (WeChat Writer v3.7.0)

单一 Skill 驱动的自动化写作流水线。支持 **"先聊后写" (Interview-First)**、**"素材转化" (Source-First)**、用于补充外部视角的 **Seed 发芽流程**，以及每次开工自动从剪藏库取料的 **剪藏找料 (Clip Scan)**。

> **运行环境**：脚本需要 Python 3.10+，纯标准库实现（writer 不依赖 Pillow，生图与图片规格验收由 wechat-director 完成）。
> 所有脚本输入路径均相对**当前调用目录**，技能自身资源以技能根目录为基准解析；不依赖机器绝对路径，macOS / Windows / Linux 通用。

## 📍 核心理念

1. **三种入口 + 一层前置能力 + 一个内置步骤**:
   - **访谈模式 (`/interview`)**: 解决冷启动，通过对话挖掘隐性知识和真实情绪。
   - **素材模式 (`/write`)**: 解决转化率，将已有笔记/链接快速转化为文章。
   - **发芽模式 (`/sprout`)**: 将外部人物、事件、故事加工成结构化 Seed，用来补足你的素材盲区。
   - **批量发芽 (`/harvest`)**: 批量处理素材库中的候选素材。
   - **剪藏找料 (Clip Scan)**: **不是入口**，而是 Stage 1 的内置步骤——每次开始写作都从剪藏库按内容支柱为本次选题取外部素材。详见 Stage 1 步骤 0。
2. **Seed 只扩素材，不改文风**: 外部 Seed 负责提供案例、反方视角和第一性问题；正文依然服从作者的第一人称真实感与风格约束。
3. **5 角色协同**: **首席记者 (Lyra)** + 呼延雷锋(大脑) + 冰清(手) + 罗永浩(眼) + 马可婷(包装)
4. **4 文件交付**: 01_Plan -> 02_Draft -> 03_Production -> Published
5. **Vibe Writing**: 坚持 "Think Aloud + 真实素材 + 外部发散 + 选题质检 + 三遍审校"
6. **角色定义**：见`references/core_personas.md`

---

## 🏗️ 目录结构规范

### 工作区根

工作区根同时含 `articles/` 与 `published/`（或位于 Obsidian vault 内、含 `.obsidian/`）。
解析顺序：**`--workspace` 显式 > `WECHAT_WORKSPACE` 环境变量 > 当前目录结构标记 > source_file 向上结构标记 > 报错**。
技能被安装到任何托管目录（`~/.claude/skills`、`~/.codex/skills` 等）都能正确定位，**不再从脚本自身位置推算**。

### 项目目录

所有工作在 `articles/Project_[Title]/` 下进行:

```
articles/Project_[Title]/
├── _source/                  # 用户提供的原始素材（Stage 1 初始化时移入）
│   ├── Raw_[Title].md        # (访谈模式) Stage 0 生成的访谈录
│   ├── Clips_[主题].md       # (剪藏找料) 从 knowledge/_inbox/ 摘出的相关外部素材
│   └── Seeds/                # (项目级) 本次写作专用发芽素材
│       └── Seed_[Topic].md
├── 01_Plan.md           # 阶段一：清洗素材 + 结构大纲 + 调研事实
├── 02_Draft.md          # 阶段二：正文初稿 (含批注，配图注入于此)
├── 03_Production.md     # 阶段三：标题方案 + 营销摘要 (无视觉)
├── Cleaned_[Name].md    # (中间产物) Stage 1 清洗结果
├── Research_Report.md   # (中间产物) Stage 1 调研报告
├── SEO_Report.md        # (中间产物) Stage 1 SEO 关键词报告
├── [Critique_Report]*.md   # (中间产物) Stage 2 审校报告
├── Directive_*.md       # (中间产物) Stage 2 综改指令
├── Storyboard.md        # (中间产物) 分镜表（wechat-director 产出）
├── zpicture.assets/     # (中间产物) 配图（wechat-director 产出，原图保留于此）
└── _temp_*.json         # (临时文件) 脚本输入文件 (可选)
```

发布产物统一位于工作区根: `published/[Title].md` + `published/zpicture.assets/`；运行数据位于 `conductor/`。

> **💡 Resume / Restart**:
> 任何时候重启任务，可使用 `/write "Title" --from-stage N` 从指定阶段继续。

> **💡 Long-Term Knowledge**:
> 可复用的 Seed 沉淀到工作区 `knowledge/seeds/`；一次性 Seed 留在当前项目目录。

---

## 🚀 工作流总览

### Pre-Stage: 发芽 (Sprout) —— 入口：`/sprout` / `/harvest`

**角色**: **主编 (呼延雷锋)** —— 分类、补料、搭桥。

**目标**: 把外部世界的人物、事件、故事加工成可被作者风格吸收的结构化 Seed。

**何时必须执行**:
1. 用户素材只有感想，没有具体人物、事件或故事抓手。
2. 用户素材过于站在自己视角里，缺乏外部案例和反方视角。
3. 文章需要补事实、案例、社会参照系，但现有素材库中没有现成条目。

**操作流程**:
1. **绑定项目 (Project Binding)**:
   - 若当前已处于某个 `Project_[Title]` 上下文，直接继承该项目。
   - 若是独立触发 `/sprout` 或 `/harvest`，优先读取 `project` 参数；若未提供，则回退读取 `title` 参数作为目标项目标题。
   - 若目标项目不存在，先创建 `articles/Project_[Title]/` 与 `_source/Seeds/`。
   - 若既没有当前项目上下文，也没有 `project/title` 可用，暂停并向用户索取项目标题；**默认不允许写 projectless Seed**。
2. **分类**: 按 `person / event / story / concept / trend` 分类，规则见 `references/routine_sprout.md`。
3. **拦截**: 若输入是 `concept`，禁止直接进入正文写作，必须先追问具体人物、事件或案例。若输入是 `trend`，走 `routine_sprout.md` 的 **`trend` 嫁接通道**（依据 `knowledge/account_positioning.md` §7 四问）：四问全过 → 降级为 `event`/`story` 放行；否则仍拦截。
4. **发芽**: 参考 `references/template_seed.md` 生成 `Seed_[Topic].md`，默认落到 `articles/Project_[Title]/_source/Seeds/`。
5. **沉淀**: 若 Seed 有长期复用价值，再晋升到工作区 `knowledge/seeds/`。
6. **衔接**: 发芽完成后进入 Stage 1，由主编把 Seed 吸收进 `01_Plan.md`。

### Stage 0: 访谈 (The Interview) —— 入口：`/interview`

**角色**: **首席记者 (Lyra)** —— 挖掘、追问、倾听。

**目标**: 无论你有多少模糊的想法，通过 5-10 轮对话，生成一份**丰满的**素材文件。

**操作流程**:
1.  **启动**: 用户输入 `/interview [话题/想法]`。
2.  **交互**: Lyra 进行苏格拉底式追问（挖掘事实细节、情绪波动、反直觉观点）。
3.  **结案**: 当用户表示"聊够了"或信息充足时，Lyra 自动整理访谈录。
4.  **产出**:
    - 创建项目目录 `articles/Project_[Title]/`
    - 将整理好的内容写入 `_source/Raw_[Title].md`
    *   **⚠️ 记录原则 (High Fidelity)**: **高保真**。禁止对用户的回答做摘要或书面化润色。必须保留第一人称、口语语气词、情绪表达和断句。我们在这个阶段需要的是"生肉"，不是"熟食"。
5.  **衔接**:
    - 自动进入 Stage 1，读取刚才生成的 `_source/Raw_[Title].md` 开始策划。

---

### Stage 1: 策划 (Plan) —— 角色：主编 (呼延雷锋) —— 策划、结构、决策。

**目标**: 无论输入多乱，输出一个坚实、经过验证的大纲。

0.  **初始化 (Init)**:
    - 创建 `articles/Project_[Title]/` 文件夹
    - **[素材模式]** 将用户提供的原始素材文件**移动**到 `_source/` 子目录（确保归档时一并迁移）
    - **[访谈模式]** 将 Stage 0 生成的 `Raw_*.md` 保留在 `_source/` 子目录
    - **[Seed 模式]** 若本次存在项目级 Seed，统一保存在 `_source/Seeds/`
    - **[剪藏找料 (Clip Scan)]** —— **每次开始写作都跑一次**，为本次选题从剪藏库捞相关素材：
      - **位置**: 工作区 `knowledge/_inbox/`（外部剪藏工具的落地区，可为软链接；不存在则跳过本步）
      - **先扫索引**: 只读每篇的 frontmatter（`title` / `date` / `tags`），**不要先读正文**。
      - **再筛**: 按 `knowledge/account_positioning.md` 的内容支柱 + 本次主题匹配标题与 tags。
      - **后读**: 只对筛出的候选（建议 0–5 条）读全文。
      - **落盘**: 摘录到 `_source/Clips_[主题].md`，并在 `01_Plan.md` 的素材摘要中引用。
      - **允许 0 条**: 找不到相关素材时，明确写下「剪藏库无相关素材」后继续，**禁止为凑数硬塞**。
      - **降级**: 若 `_inbox/` 不存在或为空，跳过本步并继续正常流程。

1.  **清洗 (Clean)**:
    - 调用 `scripts/cleaner.py` 保存 Agent 清洗后的中间文件 (`Cleaned_*.md`)。
    - **主编** 必须阅读 `Cleaned_*.md`，将其核心信息 **吸收并写入** `01_Plan.md` 的 "素材摘要" 部分。

2.  **选题质检与人机边界 (Topic Gate)**:
    - **David-HKR 质检（必做）**: 用作者的语气判断本篇是否值得写，而不是为了完成流程硬写：
      - **好奇感**: 有没有一个具体场景、反常识细节或真实问题，让读者想继续看下去？
      - **信息增量**: 读者看完能不能多知道一点事实、方法、经验或判断？
      - **共鸣感**: 这件事是否能连接到读者自己的处境，而不只是作者自说自话？
      > 及格线：至少满足两项。若只满足一项或完全不满足，先回到 `/interview` 或 `/sprout` 补素材，或请用户确认是否调整角度。
    - **写入 `01_Plan.md` 固定区块 `选题质检卡`**，至少包含：
      - 好奇感：强 / 中 / 弱，以及具体钩子
      - 信息增量：强 / 中 / 弱，以及新增价值
      - 共鸣感：强 / 中 / 弱，以及对应读者处境
      - 结论：继续 / 补素材 / 调整角度
    - **人机边界卡（必做）**: 明确哪些内容来自作者，哪些可以由 AI 辅助，哪些禁止虚构：
      - 作者原话与亲历：只能来自访谈、原始素材、旧文或用户明确补充
      - AI 可辅助：事实核查、背景知识、类比候选、结构建议、表达润色
      - 禁止虚构：第一手经历、关键情绪、人物关系、未验证数据、作者未说过的观点

3.  **SEO 关键词调研 (SEO Research)** ⚡:
    - **⚠️ 必读**: `knowledge/wechat_index_keywords.md` (查积累库)
    - 以文章主题为种子词，调用微信指数搜索相关上升词
    - 参考 `references/wechat_index_research.md` 的 SOP 进行调研
    - **产出**: `SEO_Report.md`（记录候选关键词、指数、趋势、适合嵌入的位置，以及本轮是 `采用 / weak-signal / skip SEO化` 哪种结论）
    - 将本次新发现的关键词更新到 `knowledge/wechat_index_keywords.md`
    - **过期检查**: 如积累库中相关词条"上次查时间" > 14 天，优先重新查证
    - **强制沉淀**: 主编必须把最终 SEO 结论写入 `01_Plan.md` 的固定区块 `SEO 决策卡`，至少包含：
      - 最终状态：`采用 / weak-signal / skip SEO化`
      - 最终选用词：标题主词、摘要/正文辅助词、Tags 候选
      - 放置计划：标题 / 摘要 / 开头段 / Tags
      - 禁用或降级词：不建议硬塞的词及原因
      - 备注：查无结果、仅下降词或不适合 SEO 化时的降级理由

4.  **结构 (Structure)**:
    - **⚠️ 文章类型判断（必做）**: 先确定本次写作属于哪种类型，据此决定大纲重心：
      - **现象解读型**：观察→好奇→研究→升维
      - **方法论分享型**：每节必须有可执行动作 + 坦诚说明学习成本
      - **产品体验型**：场景演示 + 真实感受
      - **调查实验型**：过程叙事 + 层层递进发现
      - **工具分享型**：个人故事铺垫→工具展示→效果惊艳
      > 若素材明显属于某类型，大纲重心应向该类型的写法重心倾斜；若类型重叠，以主要类型为准。
    - **⚠️ 必读 (Prevention)**: `knowledge/team_memory.md` (避坑指南)
    - **⚠️ 必读 (Discovery)**: `conductor/published_article_index.md` (寻找旧文关联)
    - **⚠️ 必读 (Positioning)**: `knowledge/account_positioning.md`（**账号定位卡**：四块内容支柱 + 「个人与思考」标签组、边界、热点嫁接四问。既是「剪藏找料」的筛选判据，也是 `选题质检卡` 的「共鸣感」参照——判断这篇是否落在本号支柱上）
    - **⚠️ 必读 (Inspiration)**: `knowledge/素材库.md`（**只放作者自己的观察、金句、体感**；外部链接摘要一律不在这里）
    - **⚠️ 按需 (Clips)**: `articles/Project_[Title]/_source/Clips_[主题].md`（「剪藏找料」摘出的外部素材）
    - **⚠️ 必读 (External Seeds)**: `articles/Project_[Title]/_source/Seeds/` 与 `knowledge/seeds/` (补外部案例与发散)
    - **推荐参考**: `references/template_01_plan.md`（半空白示例样本；用于把握常见章节顺序，不要求逐段照抄）
    - **主编** 制定大纲，确定核心论点、钩子和结尾。
    - **主线回扣（必做）**: 每个中段都要写清楚：
      - 本节承担什么推进任务
      - 本节结束时用哪一句自然回到核心论点
      - 开头埋下的具体细节，结尾是否能以变体形式呼应
      > 目标不是写得更花，而是避免文章变成一堆信息的堆砌。
    - **按需补充项（仅在使用 Seed 或素材明显单薄时启用）**:
      - 建议吸收 `2` 个外部案例或参照物
      - 建议加入 `1` 个反方视角
      - 建议提出 `1` 个第一性问题
    - **Seed Gate**: 进入正文前，主编应先判断本篇是否需要 `/sprout`；若未启用，也建议在 `01_Plan.md` 中简要说明"为什么当前素材已足够"。
    - **例外**: 纯个人经历、访谈回忆、生活体感类文章，如果外部材料会稀释第一人称叙事，可以不补足以上三项。
    - **吸收原则**: 外部材料只能增强判断和对照，不能覆盖作者自己的真实体验。

5.  **调研 (Research)**:
    - **顾问 (罗永浩)** 介入，(Agent进行搜索) 调用 `scripts/research.py` 格式化调研报告 (`Research_Report.md`)。
    - **主编** 将验证过的事实 (含来源链接) **填入** `01_Plan.md` 的 "事实核查表" 中。
    - **最终产出**: `01_Plan.md` (包含素材摘要、`选题质检卡`、`人机边界卡`、Seed 吸收结果、大纲、主线回扣设计、反方视角、第一性问题、验证事实，以及作为下游唯一输入源的 `SEO 决策卡`)。

🏁 **Checkpoint 1(STOP)**: 暂停并请求用户审核: `01_Plan.md` (大纲+事实+SEO关键词)。

---

### Stage 2: 撰写 (Draft) —— 角色：主笔 (冰清) —— 撰写、叙事、心流。

**目标**: 输出一篇逻辑严密、无 AI 味的初稿。

1.  **初稿 (First Draft)**:
    - **主笔 (冰清)** 参考 `01_Plan.md` 和 `knowledge/style_guide_david.md`。
    - **⚠️ SEO 消费规则**: 主笔只从 `01_Plan.md` 的 `SEO 决策卡` 读取关键词约束；若状态为 `skip SEO化`，禁止为了完成流程硬塞关键词；若为 `weak-signal`，仅允许自然使用，不强求标题或首段承载。
    - 专注于作者的语气和心流，撰写正文。
    - **⚠️ 引用旧文**: 正文中引用已发布文章时，使用纯粹的 `[[标题]]` 格式（Obsidian 会自动解析）。
    - **🖼️ 视觉重命名**: 若引用素材中有图片，必须将所有类似 `![Gemini_...|400](url)` 的乱码/默认文件名重命名为切题的 `![中文描述|400](url)`。即：**必须保留原有的尺寸参数（如 |400）**，仅修改前面的文件名部分。
    - **产出**: `02_Draft.md` (v1)。

2.  **审校 (Critique)**:
    - **顾问 (罗永浩)** 调用 `scripts/review_toolkit.py` (Critique模式) 生成体检报告 (`[Critique_Report]*.md`)。
    - **⚠️ 强制参考**: `knowledge/ai_smell_guide.md` (Anti-AI Checklist)。
    - **⚠️ 四层审校**: 必须覆盖 L1 硬规则、L2 风格一致性、L3 内容成立度、L4 老友感终审；其中 L3/L4 不通过时，即使 L1/L2 全绿，也不得判定为 `Pass`。
    - **⚠️ 方法论文章的额外检查项**: 当文章类型为「方法论分享型」时（如「怎么创建 Skill」「写作工作流拆解」），L3 内容成立度审查必须包含：
      1. **数字与时间线核查**：所有数字（十几个、几十轮、v0.1→v3.5.1 等）和时间锚点（一年前、半年前）必须对照 `Raw_*.md` 原始素材或用户明确补充核实。禁止让 AI 直接编造数字。
      2. **破折号扫描**：全篇破折号 `——` 数量应为 0（全改成逗号或分句）。这是最常见的 AI 味暴露点。
      3. **「不是X是Y」句式扫描**：检测并替换所有「不是...是...」「不是说...是...」反转句式，改为更自然的「是...不...」或口语化表达。
    - **⚠️ 中间产物落盘**: 必须**先写入文件**，再在对话中汇报摘要。禁止跳过文件直接输出。
    - **⛔ 审校完成后，不要直接修改文章，必须进入步骤 3 综改。**

3.  **综改 (Refine)** ⚠️ 不可跳过:
    - **主编 (呼延雷锋)** 调用 `scripts/review_toolkit.py` (Directive模式) 生成综改指令 (`Directive_*.md`)。
    - **⚠️ 中间产物落盘**: 必须**先写入文件**，再在对话中汇报摘要。禁止跳过文件直接输出。
    - **主笔 (冰清)** 根据指令执行修改。
    - **产出**: `02_Draft.md` (v2)。

🏁 **Checkpoint 2 (STOP)**: 暂停并请求用户审核 `02_Draft.md` (正文内容)。如需配图，文本定稿后转 `/draw`。

> **L4 老友感终审（请在审核时同步完成）**：
> 读完全文，感觉是一个真实的人在认真聊一件打动他的事，还是一个 AI 在输出信息？
> - 如果任何段落让你觉得"这段 AI 味太重了"，指出具体段落。
> - 重点关注：情绪表达是否像体感记忆（"我当时就愣住了"）而非知识性描述；有没有理中客的中立感；有没有只有 AI 才能编出来的案例细节。

---

### Stage 3: 制作 (Production) —— 角色：制作人 (马可婷) —— 包装、传播、归档。

**目标**: 赋予文章传播力（标题、包装）。

1. **定题 (Title)**:
    - **主编 (呼延雷锋)** 生成 4 个标题方案：
      - **SEO 关键词型**（优先从 `01_Plan.md` 的 `SEO 决策卡` 中选择已批准的词嵌入）
      - 情绪共鸣型（不卖焦虑）
      - 问题共鸣型
      - 反常识型
    - **同时生成 `slug`**（英文短链，用于 URL）

2. **包装与 Frontmatter (Marketing & Frontmatter)**:
    - **制作人 (马可婷)** 撰写摘要 (Excerpt)、转发语、挑选 Tags 并生成标准 Frontmatter。
    - **Frontmatter 生成规则**:
      1. 包含 `title`, `date` (YYYY-MM-DD), `slug`, `excerpt` (50-100字), `tags`, `cover`, `status: published`。
      2. **Tags 官方白名单规则**: `tags` 必须从以下 36 个官方白名单中挑选 2-4 个，严禁自行创造标签：
         - **知识管理类**: `Obsidian`, `Obsidian入门`, `知识管理`, `Obsidian插件`, `笔记同步`, `Web剪藏`
         - **AI与智能体**: `AI Agent`, `AI模型`, `Claude Code`, `Codex`, `WorkBuddy`, `OpenClaw`, `提示词工程`, `MCP`
         - **效率与工具**: `效率工具`, `自动化`, `苹果生态`, `终端命令行`, `Raycast`, `Typeless`, `任务管理`
         - **编程与开源**: `编程开发`, `AI编程`, `开源`
         - **创作与发布**: `内容创作`, `微信公众号`, `WeChat Converter`, `多平台分发`, `排版与导出`
         - **运维与建站**: `服务器运维`, `SEO与数据分析`
         - **个人与思考**: `生活随笔`, `个人成长`, `职场思考`, `复盘与踩坑`, `副业与出海`
      3. **摘要规范**: Excerpt 控制在 **50-100 字**（兼顾个人主页列表页展示与微信后台限制，微信硬上限 120 字）。在 Stage 3 产出时完成控制，禁止依赖 Stage 4 脚本截断。
      4. **⚠️ SEO 消费规则**: Excerpt 与 Tags 必须先读取 `01_Plan.md` 的 `SEO 决策卡`；若状态为 `skip SEO化`，以自然表达优先；若为 `weak-signal`，仅轻量吸收相关词，且所选 Tag 必须落在 36 个白名单内，不得堆砌。
      5. **Obsidian 专题页规则**:
         - 如果文章主题和 Obsidian 明确相关，Frontmatter 的 `tags` 必须包含 `Obsidian`。
         - 若文章适合按学习路径收录到 Obsidian 专题教程中，请额外添加 `obsidianSection` 字段，取值范围必须为以下 8 个之一：
           `first-steps | basics | plugins-automation | advanced-organization | ai-workflow | collecting | sync-backup | publishing`（阶段含义见 `references/io_schema.md`）。
         - 如果文章属于系统教程系列，最终标题必须使用 `Obsidian 入门70：文章标题` 这种格式，`入门` 和数字中间不要空格。随笔或独立工具评测等非编号文章不得强行编号。

3. **视觉 (Visual)**:
    - **Handoff**: 文本定稿后，请提示用户运行 `/draw` 进行配图。

🏁 **Checkpoint 3**: 审核 `03_Production.md` (标题/摘要)。

---

### Stage 4: 归档 (Archive) —— 角色：制作人 (马可婷) —— 包装、传播、归档。

**目标**: 发布准备完成，并沉淀团队记忆。

1. **图片 SEO 巡检 (Image SEO Gate)**:
    - 发布前必须先读取 `02_Draft.md`、`03_Production.md`，以及 `01_Plan.md` 的 `SEO 决策卡`。
    - 扫描正文中的图片语法，包括 `![...](...)` 与 `![[...]]`。若正文尚未插入任何图片，必须暂停并提醒用户：`当前文章尚未插入图片，是否先暂停归档，待插入图片后再继续？` 用户明确继续后，才允许无图归档。
    - 对每张图片结合所在小节、前后段落、最终标题、摘要、Tags 与已批准 SEO 关键词，生成适合个人网站 alt 的图片显示名。
    - 命名规则：具体、自然、与画面和文章主题相关；可吸收 1 个贴切 SEO 关键词，但禁止堆砌关键词；避免 `Pasted image`、`Screenshot`、`IMG_`、`Gemini_`、随机哈希等无意义名称。
    - 修改 Obsidian 草稿时保留尺寸参数，只改尺寸参数前面的显示名，例如 `![Gemini_xxx|400](url)` 改为 `![Obsidian 图片外链失效示意图|400](url)`。不要改动图片 URL。
    - `|400`、`|300x200` 等 Obsidian 显示尺寸在归档稿中继续保留，用来保证 Obsidian 与公众号准备稿的预览体验；不要在 `scripts/archive.py` 中删除。
    - 个人网站生成时，应在网站构建层解析图片 alt：把 `![描述|400](url)` 输出为干净 alt（`描述`），同时用网站 CSS 或图片组件控制展示尺寸，避免图片按原始像素撑大页面。

2. **发布 (Publish)**:
    - 调用 `scripts/archive.py`（自动执行 Frontmatter 合规校验：Tags 36 白名单、摘要 50-100 字、obsidianSection 取值）
    - 生成 `published/[Title].md`（Frontmatter 后直接接正文，无空行、无一级标题）
    - **复制**项目 `zpicture.assets/` 到 `published/zpicture.assets/`（原图保留在 `articles/`）
    - **项目保留**: `articles/Project_[Title]/` 原位保留，不再移动到 `conductor/archive/`
    - **自动更新**: `conductor/published_article_index.md`
    - 可选参数 `--workspace <路径>`：显式指定工作区根，规避自动检测歧义。

3. **记忆 (Memorize)**:
    - 脚本会把本次建议写入 `conductor/pending_memory_suggestions.json`，并提示用户确认后再写入 `knowledge/team_memory.md`（不静默写入）。

🏁 **Checkpoint 4**: 确认归档完成。

---

## 🛠️ 脚本工具箱 (Scripts)

| 脚本                          | 功能                    | I/O 规范                      |
| :-------------------------- | :-------------------- | :-------------------------- |
| `scripts/workspace.py`      | 工作区根解析（显式 > 环境变量 > 结构标记） | 被同目录脚本 import |
| `scripts/cleaner.py`        | 保存清洗后内容               | 见 `references/io_schema.md` |
| `scripts/research.py`       | 格式化调研报告 (Input: JSON) | 见 `references/io_schema.md` |
| `scripts/review_toolkit.py` | 批评、审读、指令生成            | 见 `references/io_schema.md` |
| `scripts/archive.py`        | 归档、图片复制、索引更新          | 见 `references/io_schema.md` |
| `scripts/article_assets.py` | 稿件图片引用解析与可移植复制         | 被 `archive.py` import |
| `scripts/material_store.py` | 用户确认后保存素材 / 项目 Seed / 长期 Seed | 见 `references/io_schema.md` |
| `scripts/memory_store.py`   | 用户确认后写入或撤销团队记忆        | 见 `references/io_schema.md` |
| `scripts/config_check.py`   | 首次使用前检测 Python、Obsidian CLI、writer 脚本与可选服务 | — |

> 详细 JSON Schema 请参考 `references/io_schema.md`

---

## 📖 参考文档 (References)

- `references/core_personas.md`: 5大核心角色人设详情（含首席记者）
- `references/routine_sprout.md`: 外部素材发芽规则
- `references/routine_harvest.md`: 批量收获规则
- `references/template_seed.md`: Seed 模板样例
- `references/template_01_plan.md`: `01_Plan.md` 半空白示例样本
- `references/wechat_index_research.md`: 微信指数 SEO 调研 SOP
- `knowledge/style_guide_david.md`: 作者写作风格（示例，需替换为你的风格）
- `knowledge/ai_smell_guide.md`: 去AI味审校清单
- `knowledge/wechat_index_keywords.md`: 微信指数关键词积累库
- `references/io_schema.md`: 交付文件规范

# Knowledge Base (知识库)

此目录存放 "David Writing Team - Wechat-writer" 的共享知识、规则标准和参考文档。

## 🎯 用途 (Purpose)
为 Skill 提供统一的、静态的**上下文 (Context)** 和 **标准 (Standards)**。

## 🚫 边界 (Boundaries)
*   **不存放代码**: 可执行脚本请放入 `Skills/<skill-name>/scripts/`。
*   **不存放人设**: Agent 的 Prompt 请放入 `references/`。
*   **不存放 SOP**: 具体的操作步骤 (Routine) 请放入 `Skills/<skill-name>/references/`。

## 📂 文档列表
1.  **`style_guide_david.md`**: 大卫个人写作风格指南 (平和、自然、从容)。
2.  **`ai_smell_guide.md`**: 降 AI 味操作指南与必删词表。
3.  **`team_memory.md`**: 团队长期记忆与动态规则 (由鲁迅自动更新)。
4.  **`published_article_index.md`**: 历史文章索引 (用于内链推荐)。
5.  **`素材库.md`**: 私有灵感、金句、碎片观察和原始选题池。
6.  **`seeds/`**: 结构化外部素材库。只存已经证明有复用价值的长期 Seed。

## 🌱 `素材库.md` vs `seeds/`

两者边界必须清晰：

*   **`素材库.md`**: 原料仓。允许碎片、半成品、金句、随手记、还没想清楚的观察。
*   **`seeds/`**: 精加工仓。只放已经结构化、可被 Stage 1 稳定调用的 Seed。

**原则**:
*   默认先在项目目录 `_source/Seeds/` 里生成项目级 Seed。
*   只有确认可以跨项目复用的 Seed，才晋升到 `knowledge/seeds/`。
*   `seeds/` 负责补案例、补反方视角、补第一性问题，不负责改写 David 的风格。

## 🔗 引用方式
在 Skill 或 Agent 文件中引用时，请使用相对路径：
`knowledge/style_guide_david.md` (如果在 Skill 根目录下)

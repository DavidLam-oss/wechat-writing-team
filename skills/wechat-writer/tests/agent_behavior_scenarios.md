# Writer Agent 行为验收场景

这些场景用于人工或子智能体验收技能规则，不是 Python 单元测试。

1. 普通聊天出现一段可能有价值的经历：必须先询问保存到素材库、当前项目 Seed 或暂不保存。
2. `/sprout` 没有项目上下文：必须索取项目标题，不能写 projectless Seed。
3. Seed 可能跨项目复用：必须显示晋升确认，用户未确认时只能保留项目级 Seed。
4. 归档产生团队经验：必须显示写入、暂不写入、修改后写入三项选择。
5. 用户选择保存后：只能写入当前工作区的 `knowledge/` 或 `articles/Project_[Title]/_source/Seeds/`。

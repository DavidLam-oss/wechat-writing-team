---
title: "900+ 个恶意 IP 之后，我做了第三步：让 OpenClaw 对公网“不可见”"
---

## Visual Storyboard

### Part A: 主视觉 cover-main (2.35:1)
(IP形象: 是)
```text
movie composition, 2.35:1 aspect ratio, 扁平矢量插画 + 贴纸风格, 厚白描边, 低饱和深夜蓝与冷灰配色, 电影感光影与轻微颗粒, 场景: 一台小小的云服务器像一间街角小屋, 门口有微弱的光, 远处有雷达扫描的光束扫过但在门前“断掉/消失”, 空气里漂浮很多红色小点(代表恶意IP)但都被挡在远处, 前景出现 IP 形象: A bald Asian male (early 30s), wearing signature bright red round-framed glasses, neat goatee beard on chin. Character has thick white outlines around the entire silhouette (sticker style). 他神情平静, 手里拿着一把钥匙, 身后的小屋窗内有一个抽象的“爪子”形状符号发出柔和光(不含任何品牌logo), no watermark, no text --ar 2.35:1
```

### Part B: 侧边栏 cover-sidebar (1:1)
(IP形象: 否)
```text
纯色背景，主色调深夜蓝（与主视觉一致），中心放置中文文字两行排版：上行「对外」，下行「不可见」，字形厚重圆润，白色或浅米色，高对比，贴纸风格轻微投影，无任何英文，无水印
```

### Part C: 内文配图 illustration

#### 插图 1: 把门藏起来（情绪钩子）
(IP形象: 是)
```text
portrait composition, 3:4 aspect ratio, 扁平矢量插画 + 贴纸风格, 厚白描边, 场景: 一扇“门”正在被拉上一层半透明的雾幕/幕布, 雾幕后面隐约是服务器机箱的轮廓, 门外飘着许多红色小点(恶意IP)四处乱撞, 但雾幕让门的位置变得难以辨认, IP 形象: A bald Asian male (early 30s), wearing signature bright red round-framed glasses, neat goatee beard on chin. Character has thick white outlines around the entire silhouette (sticker style). 他在一旁把幕布轻轻拉好, 表情放松, 画面留足负空间, 无文字, 无水印
```
> Context: "把门藏起来。"

#### 插图 2: 日志刷屏的压迫感
(IP形象: 否)
```text
portrait composition, 3:4 aspect ratio, 扁平矢量插画 + 贴纸风格, 厚白描边, 场景: 深色背景里一块竖直的“终端窗口”像雨幕一样往下刷, 不是具体文字, 而是一排排抽象的短横线与红色警示点, 形成“刷屏”的节奏, 终端窗口外侧有很多来自不同方向的红色点状流线冲过来, 画面中心偏上留白用于呼吸, 无文字, 无水印
```
> Context: "按理说，它不该这么热闹。"

#### 插图 3: 先用云安全组做白名单（更稳的第一步）
(IP形象: 是)
```text
portrait composition, 3:4 aspect ratio, 扁平矢量插画 + 贴纸风格, 厚白描边, 场景: 一朵简化的“云”图标前方悬浮着一张“规则卡片”, 卡片上用抽象图形表达“只允许一个来源通过”(一条绿色通道)而其他来源都是灰色被挡回去, 不出现任何真实厂商界面或logo, IP 形象: A bald Asian male (early 30s), wearing signature bright red round-framed glasses, neat goatee beard on chin. Character has thick white outlines around the entire silhouette (sticker style). 他用手指轻点规则卡片, 表情像是在说“先从这一步开始就行”, 画面干净, 无文字, 无水印
```
> Context: "如果你问我现在更推荐哪条路：先从云安全组开始。"

#### 插图 4: filtered 的世界安静了
(IP形象: 否)
```text
portrait composition, 3:4 aspect ratio, 扁平矢量插画 + 贴纸风格, 厚白描边, 场景: 一束扫描光从画面左侧扫向右侧的服务器小屋, 光束在靠近小屋门口时变得断断续续并消失, 门口前方有一圈柔和的透明屏障(代表DROP/过滤), 红色小点被挡在屏障外侧形成一圈, 屋内是温暖的微光, 对比强烈, 无文字, 无水印
```
> Context: "它摸不到门把手。"

#### 插图 5: Fail2ban 第二张网
(IP形象: 是)
```text
portrait composition, 3:4 aspect ratio, 扁平矢量插画 + 贴纸风格, 厚白描边, 场景: 一张半透明的网罩在服务器小屋外侧, 网眼里卡着许多红色小点, 少数红点被网“弹开”飞出去, IP 形象: A bald Asian male (early 30s), wearing signature bright red round-framed glasses, neat goatee beard on chin. Character has thick white outlines around the entire silhouette (sticker style). 他像门卫一样站在网旁边, 手里拿着一个小印章/警示牌(不含文字), 表情平静但坚定, 无文字, 无水印
```
> Context: "Fail2ban 就像第二张网。"

#### 插图 6: 兜底入口（备用钥匙）
(IP形象: 是)
```text
portrait composition, 3:4 aspect ratio, 扁平矢量插画 + 贴纸风格, 厚白描边, 场景: 一把大大的备用钥匙与一架简化的“安全梯/救生绳”从云端垂下来, 连接到服务器小屋的侧面小窗, 象征控制台兜底入口, 画面下方有被锁在门外的影子(抽象), 但通过侧窗能重新进入, IP 形象: A bald Asian male (early 30s), wearing signature bright red round-framed glasses, neat goatee beard on chin. Character has thick white outlines around the entire silhouette (sticker style). 他握着钥匙露出松一口气的表情, 无文字, 无水印
```
> Context: "VNC 就是那把备用钥匙。"


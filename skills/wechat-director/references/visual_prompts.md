# Visual Prompts & Style Guide (v3.0 - Chinese)

> **Source**: `Prompt/文章配图（含 IP 形象） - Prompt.md`
> **Role**: 张艺谋 (Visual Director)
> **Engine**: Flux / Nano Banana Pro (中优)

## 🎨 核心风格 (Core Style)

**扁平矢量贴纸风格 (Flat Vector Illustration with Sticker Style)**

*   **Global Style Lock**: 确保这组关键词在所有 Prompt 中出现。
*   **Keywords**: `扁平矢量插画`, `白色贴纸描边`, `极简主义`, `鲜艳配色`, `干净的矢量线条`, `白底`, `商业插画`, `Dribbble风格`, `无阴影`, `2D扁平`.

## 👤 IP 形象 (Character LoRA)

> **The "IP Rule"**: 必须在 `(IP形象: 是)` 时强制包含以下核心描述。

### 1. 核心特征 (Base)
```text
一个光头亚裔男性(30岁左右)，戴着标志性的明亮红色圆框眼镜，下巴留着整洁的山羊胡。人物全身轮廓有粗白色描边(贴纸风格)。
```

### 2. 动态换装 (Dynamic Clothing)
*   **Context Aware**: 不要默认穿T恤。根据场景换装：
    *   *创业/代码*: 连帽衫 (Hoodie)，休闲T恤。
    *   *商务*: 西装外套，衬衫。
    *   *居家/放松*: 宽松毛衣。

## 📐 构图规范 (Composition)

### 1. 主视觉封面 (Cover Main) --ar 2.35:1
*   **Prompt Structure**:
    ```text
    [场景描述], [IP核心特征] 穿着 [场景对应服装], [背景环境], 扁平矢量插画, 白色贴纸描边, 极简主义, 鲜艳配色, 干净线条, 白底, --ar 2.35:1
    ```

### 2. 侧边栏 (Cover Sidebar) --ar 1:1
*   **Requirement**: **纯色背景** (提取主视觉主色调).
*   **Prompt Structure**:
    ```text
    纯色 [主视觉主色调] 背景, 画面中心是一个 [代表主题的物体/图标], 极简主义, 扁平矢量插画, 白色贴纸描边, 无文字, --ar 1:1
    ```

### 3. 内文配图 (Insert) --ar 3:4
*   **Prompt Structure**:
    ```text
    [具体动作/交互], [IP核心特征 (如需)] 穿着 [场景对应服装], [简单背景], 扁平矢量插画, 白色贴纸描边, 极简主义, --ar 3:4
    ```

## 🚫 负向提示 (Negative Prompt)
```text
照片, 真实感, 3d, 阴影, 渐变, 复杂细节, 凌乱, 文字, 水印, 签名, 模糊, 低质量, 素描
```

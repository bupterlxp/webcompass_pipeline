/*
  style_name: Cyber-Industrial Precision (赛博工业精密风)
  style_user_impression: 就像是拆开了精密仪器的外壳，直接注视着裸露的电路板与机械结构。没有多余的柔光和阴影掩饰，强调结构美学、数据密度与绝对的秩序感。
  style_animation_vibe: 机械传动式的干脆利落，像快门闭合或终端代码刷新。没有呼吸感，只有“开/关”的二进制状态切换和数据流的瞬间加载。
  palette_hex: #050505 (Deep Matter), #171717 (Panel Grey), #E5E5E5 (Primary Text), #CCFF00 (Acid Lime - Accent)
  ui_framework: Tailwind CSS
*/

==============================
A. 页面基础输入信息
==============================
【页面主要语言】English
【排版特征】Monospaced-mix (等宽混排), Grid-locked (严格网格对齐)
【页面目标】展示工具的硬核性能与可配置性
【受众画像】全栈开发者、系统架构师、硬核科技爱好者
【一句话价值主张】Deconstruct. Build. Deploy.
【三条核心卖点】
1. Raw control: Direct access to code-level configurations via visual UI.
2. Military-grade encryption: Zero-knowledge architecture by default.
3. Protocol-based messaging: Email reimagined as a data stream.
【信任要素】右侧显示实时的系统状态看板（System Status: All Systems Operational, Uptime: 99.99%）代替传统头像。
【行动按钮文案】主按钮：Initialize System / Start Terminal；次按钮：Read Documentation

==============================
B. 全局通用视觉规范（User -> Design -> Tech）
==============================
- 视觉一致性：
  - [用户感受]：页面像一张巨大的工程蓝图，所有的区域都被清晰的线条分割，没有模糊地带。
  - [设计原理]：**结构显性化（Structural Brutalism）**，摒弃所有装饰性的阴影和圆角，让**分割线（Dividers）**和**容器（Containers）**成为视觉主体。
  - [技术实现]：`bg-neutral-950`, `border-neutral-800`, `rounded-none` (直角)
- 色彩系统：
  - [用户感受]：背景很深很实，关键按钮用了极亮的酸性绿，非常刺眼（褒义），像警告灯一样醒目。
  - [设计原理]：**高能警示色（High-Vis Accent）**，在低饱和度的灰阶背景上，使用**荧光色（Neon/Acid）**作为唯一的交互引导色。
  - [技术实现]：Background: `#050505`; Accent: `#CCFF00` (Lime-400/500); Text: `text-neutral-200`
- 字体系统：
  - [用户感受]：标题像打字机打出来的代码，正文很客观冷静。
  - [设计原理]：**系统代码美学（System Aesthetic）**，标题和元数据强制使用**等宽字体（Monospace）**，强调技术属性；正文使用无衬线字体保证可读性。
  - [技术实现]：Headings/Meta: `font-mono (JetBrains Mono/Fira Code)`, Body: `font-sans (Inter/Roboto)`
- 图标系统：
  - [用户感受]：图标是实心的、方方正正的，像像素点或者乐高积木。
  - [设计原理]：**像素/块状图标（Block/Pixel Icons）**，使用填充风格（Filled）或粗线条，强调稳固感。
  - [技术实现]：Phosphor Icons (Fill/Bold weight), `text-white`
- 组件系统：
  - [用户感受]：按钮按下去是硬的，没有渐变，只有颜色的瞬间反转。
  - [设计原理]：**平面反转（Flat Inversion）**，交互状态通过背景色与文字颜色的互换来体现，模拟老式终端的光标效果。
  - [技术实现]：Default: `border border-white text-white`; Hover: `bg-white text-black`
- 图像/装饰：
  - [用户感受]：背景里有若隐若现的网格纸纹理，还有随机跳动的数字代码。
  - [设计原理]：**参数化背景（Parametric Background）**，使用**精密网格（Micro-Grid）**和**数据噪点（Data Noise）**作为装饰。
  - [技术实现]：CSS `background-image: radial-gradient(...)` dots pattern, `border-r` vertical guides.

==============================
C. 全局交互与动效规范
==============================
- 基础交互反馈（Hover/Active）：
  - [用户感受]：鼠标滑过的地方，会突然出现一个方框框住它，或者颜色直接反转，很干脆。
  - [设计原理]：**状态突变（State Snap）**，取消 `transition-all` 的平滑过渡，使用极快的时间（<100ms）或无过渡，强调机械响应速度。
  - [技术实现]：`hover:bg-[#CCFF00] hover:text-black`, `duration-75`
- 进场动画（Scroll Entry）：
  - [用户感受]：像是系统正在加载模块，一个个方块拼贴出来。
  - [设计原理]：**交错构建（Staggered Construct）**，元素不透明度从0到1跳变，配合裁切效果（Clip-path reveal）。
  - [技术实现]：`animate-pulse` briefly then `opacity-100`, no slide-in.
- 持续动态（Ambient Motion）：
  - [用户感受]：角落里有光标在不停地闪烁，数据面板上的数字在跳动。
  - [设计原理]：**实时遥测（Live Telemetry）**，模拟系统监控数据的实时刷新。
  - [技术实现]：`animate-blink` (cursor), JS-based number ticker.

==============================
D. 全局通用排版规范（User -> Design -> Tech）
==============================
- 栅格与对齐：
  - [用户感受]：看起来像Excel表格或者报纸排版，线就是线，框就是框。
  - [设计原理]：**显性网格系统（Explicit Grid System）**，不仅使用不可见的网格对齐，更直接用**可见的1px线条**画出网格结构。
  - [技术实现]：`border-l border-r border-neutral-800`, `grid-cols-12`
- 信息层级：
  - [用户感受]：通过字号大小区分不明显，更多是通过“加粗”、“全大写”或者“加框”来区分。
  - [设计原理]：**形式追随功能（Form Follows Function）**，利用标签（Tags/Badges）和全大写（Uppercase）来标记元数据。
  - [技术实现]：Meta: `uppercase text-xs tracking-widest text-neutral-500`
- 间距体系：
  - [用户感受]：内容排得很密，信息量很大，有点像彭博终端。
  - [设计原理]：**高密度信息流（High Density Stream）**，减少不必要的留白，强调效率。
  - [技术实现]：`gap-4`, `p-4` or `p-6` (compact padding).

==============================
E. 模块级规范（变异版结构）
==============================

【模块1：Hero Section（首屏）】
- 模块目标：展示核心控制台，强调“控制权”。
- 排版规范：
  - [用户感受]：左边是巨大的命令行标题，右边是一个看起来很复杂的代码编辑器窗口。
  - [设计原理]：**分屏控制台（Split Console）**，左侧叙事，右侧演示操作环境。
  - [技术实现]：Grid `grid-cols-1 lg:grid-cols-2`, full height borders.
- 视觉规范：
  - [用户感受]：输入框像是一个终端命令行，前面有个 `>` 符号并在闪烁。
  - [设计原理]：**CLI界面模拟（Command Line Interface）**。
  - [技术实现]：Input font `font-mono`, prefix `>`, cursor `animate-pulse`.

【模块2：Feature Showcase (Blueprint Mode)】
- 模块目标：解构建站过程。
- 排版规范：
  - [用户感受]：不是斜着的3D图，而是一张平面的、像蓝图一样的线框图，上面标了很多尺寸和注释。
  - [设计原理]：**工程图解（Engineering Schematic）**，使用平面线框图（Wireframe）配合引出线（Callouts）标注功能细节。
  - [技术实现]：SVG lines connecting text to specific parts of the UI image. Flat `border-2`.

【模块3：Feature Grid (Modular Blocks)】
- 模块目标：展示功能模块。
- 排版规范：
  - [用户感受]：像仓库里的货架，一个个格子里放着不同的零件（功能）。每个格子都有编号（01, 02, 03）。
  - [设计原理]：**索引卡片（Index Cards）**，每个功能点被封装在严格的边框内，左上角带有数字索引。
  - [技术实现]：`border border-neutral-800`, `aspect-square`, internal padding.

【模块4：Security Visualization (Firewall)】
- 模块目标：展示防御能力。
- 排版规范：
  - [用户感受]：不再是雷达，而是一堵厚厚的墙，或者是不断滚动的加密代码流（Matrix风格，但是是灰白色的）。
  - [设计原理]：**数据流瀑布（Data Waterfall）**，强调数据的加密与不可读性。
  - [技术实现]：Text scrolling vertically masked by gradient, strictly monospaced.

【模块5：Feature Showcase (Data Stream Email)】
- 模块目标：展示邮件功能的原始数据感。
- 排版规范：
  - [用户感受]：展示的不是漂亮的邮件界面，而是JSON格式的数据包，被自动解析成了可读内容。
  - [设计原理]：**代码可视对比（Code vs Visual）**，左侧展示Raw Data，右侧展示Rendered View，强调“Zero Config”。
  - [技术实现]：Two column layout within a container, syntax highlighting colors.

【模块6：Feature Grid (Protocol Specs)】
- 模块目标：罗列技术参数。
- 排版规范：
  - [用户感受]：一个密密麻麻的参数列表，像服务器的配置单。
  - [设计原理]：**规格清单（Spec Sheet）**，使用列表（List）而非卡片，强调密集的技术参数。
  - [技术实现]：`divide-y divide-neutral-800`.

【模块7：Pricing / Terminal Access】
- 模块目标：引导开始免费使用。
- 排版规范：
  - [用户感受]：一个巨大的、带边框的区域，中间只有一个闪烁的按钮：“INITIATE FREE TIER”。背景是斜纹警示线。
  - [设计原理]：**工业警示区（Hazard Zone）**，利用斜纹（Stripes）和高对比度色彩吸引点击。
  - [技术实现]：Background `repeating-linear-gradient(45deg, ...)` opacity-10.

==============================
F. 输出要求（针对硬核工程风格优化）
==============================
1. **技术栈**：使用 Tailwind CSS (CDN)。
2. **字体策略**：
   - 标题与数据：`font-family: "JetBrains Mono", "Fira Code", monospace;`
   - 正文：`font-family: "Inter", system-ui, sans-serif;`
3. **关键样式实现**：
   - **Grid Lines**：使用 `div` 配合 `absolute inset-0` 和 `grid` 绘制背景网格线。
   - **Acid Accent**：使用 `text-[#CCFF00]` 或 `bg-[#CCFF00]` 实现高亮。
   - **Glitch Effect**：尝试在 Hover 状态下使用 `translate-x` 模拟轻微抖动。
4. **文案内容**：
   - 保持原意但语气更冷峻（例如 "Create amazing websites" -> "DEPLOY WEB INTERFACE"）。
5. **代码结构**：
   - 使用语义化标签，但为了视觉效果，可以多层嵌套 `border` 容器。
   - 必须实现“光标闪烁”和“机械反转Hover”效果。
6. **图片资源**：
   - 使用 **Unsplash** 获取工业、服务器、线路板相关图片（关键词：Server room, Circuit board, Blueprint, Abstract geometry）。
   - 图片需处理为黑白或低饱和度，以配合整体风格。
7. **纯净输出**：只输出 HTML 代码。
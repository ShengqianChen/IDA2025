## 前端显示优化改动说明

本文件总结本次在前端完成的三项显示能力优化：
1) Markdown 与代码高亮渲染
2) 日志级别高亮（INFO/WARN/ERROR/FATAL）
3) 响应式布局优化
4) 明/暗主题一键切换

每个模块包含：改动文件与关键行、实现方法、功能作用。

---

### 模块一：Markdown 与代码高亮渲染

- 改动文件与关键行
  - `src/components/ChatMessage.vue`
    - `<script setup>` 中引入与配置（约第 17–52 行）：
      - 引入 `marked` 与 `highlight.js`
      - `marked.setOptions({...})` 配置 GFM、换行，以及 `highlight` 回调对代码块进行语法高亮
    - 安全转义与渲染流程（约第 24–52、57–86 行）：
      - 定义 `escapeHtml` 方法用于“用户消息”的 HTML 转义
      - 计算属性 `formattedContent`：AI 消息走 Markdown 渲染；用户消息保持转义后的纯文本
    - 模板绑定（约第 8–13 行）：
      - 使用 `v-html="formattedContent"` 渲染富文本
  - `src/assets/styles.css`
    - highlight.js 主题样式（文件底部约第 115 行开始）：统一深色代码块背景与各语法元素配色

- 使用的方法
  - 采用 `marked` 实现 Markdown → HTML 渲染
  - 采用 `highlight.js` 在 `marked.setOptions` 的 `highlight` 回调中实现代码高亮
  - 对“用户消息”先通过 `escapeHtml` 转义再参与关键字高亮，避免 XSS 风险；“AI 消息”支持 Markdown 与代码高亮

- 功能作用
  - 支持标题、列表、表格、引用、代码块等 Markdown 语法
  - 提升技术类内容（如报错堆栈、配置片段）的可读性与结构化展示效果

---

### 模块二：日志级别高亮（INFO/WARN/ERROR/FATAL）

- 改动文件与关键行
  - `src/components/ChatMessage.vue`
    - 计算属性 `formattedContent`：仅保留错误级别词高亮（大小写不敏感 `.../gi`）
      - 级别：`ERROR|FATAL|WARN|WARNING|INFO|INFORMATION|DEBUG`
    - 样式（`:deep` 作用域）仍沿用 `.error-level` 与四种状态色：
      - `.error-fatal`（红）、`.error-warn`（橙）、`.error-info`（蓝）、`.error-debug`（绿）

- 使用的方法
  - 简化为只对日志级别词做替换 → `<span class="error-level error-xxx">...</span>`
  - 移除服务名与错误码的匹配与渲染逻辑，避免误高亮与未闭合标签问题

- 功能作用
  - 以最小复杂度提供关键信息的视觉分层
  - 减少误命中与排版干扰，保证显示稳定

---

### 模块三：响应式布局优化

- 改动文件与关键行
  - `src/views/Chat.vue`
    - 响应式断点（`@media (max-width: 768px)` 与 `@media (max-width: 480px)`，约样式段落第 243 行后）：
      - 平板（≤768px）：
        - 布局从左右两栏切换为上下结构（`chat-container` 改为 column）
        - `sidebar` 下移到页面下方（`order: 2`）、宽度占满、`max-height` 限制
        - 操作按钮区域从纵向改横向等分（子项 `flex: 1`）
        - 标题字号、消息区 padding 缩小
      - 手机（≤480px）：
        - 进一步压缩 `sidebar` 高度（`max-height: 150px`）
        - `chat-area` 高度自适应：`height: calc(100vh - 150px)`
        - 标题、按钮尺寸进一步收紧；滚动条改为细样式
    - 其他样式注释：
      - 滚动容器 `.messages-container` 启用平滑滚动与自定义窄滚动条
      - 增加 `min-width: 0` 防止 flex 子元素溢出
  - `src/components/ChatMessage.vue`
    - 组件级响应式（文件末尾两段 `@media`）：
      - 中小屏缩小头像尺寸、气泡内边距、文本与代码块字号，防止消息溢出并保持可读性

- 使用的方法
  - 纯 CSS 媒体查询（不引入额外依赖）按断点重排布局与控制尺寸
  - 对关键容器（如 `.chat-area`、`.messages-container`）增加溢出与滚动优化

- 功能作用
  - 在平板与手机端保持良好的信息密度与操作体验
  - 有效避免小屏设备上“侧边栏挤占主区”“消息溢出”问题

---

### 模块四：明/暗主题一键切换

- 改动文件与关键行
  - `src/assets/styles.css`
    - 新增暗色主题变量覆盖（约第 30 行后）：
      - `[data-theme="dark"] { ... }` 定义暗色模式下的 `--bg-color`、`--card-bg`、`--text-*`、`--border-color`、`--user-message`、`--bot-message` 等变量
  - `src/views/Chat.vue`
    - 头部新增切换按钮（模板约第 25–33 行）：
      - `<button class="secondary" @click="toggleTheme">{{ themeLabel }}</button>`
    - 初始化与切换逻辑（脚本约第 59 行起）：
      - `onMounted` 中读取 `localStorage.theme`，若无则跟随系统 `prefers-color-scheme`
      - `document.documentElement.setAttribute('data-theme', theme)` 应用主题
      - `toggleTheme()` 在 `light/dark` 间切换并持久化到 `localStorage`

- 使用的方法
  - 基于 CSS 变量的主题切换：通过切换根节点的 `data-theme` 属性选择不同变量组
  - 不影响现有组件样式，仅变量取值不同即可完成主题切换

- 功能作用
  - 提供明/暗主题的快速切换，适应环境光与用户偏好
  - 主题状态持久化，刷新页面仍保持用户的选择

---



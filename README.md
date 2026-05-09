# chatAI

基于 Vue 3 的 AI 对话 Web 应用，支持流式响应与 Markdown 渲染。

## 技术栈

| 类别 | 技术 |
|------|------|
| 框架 | Vue 3 + TypeScript |
| 构建 | Vite 8 |
| UI | Naive UI + Tailwind CSS v4 + SCSS |
| 状态管理 | Pinia（持久化） |
| LLM API | DeepSeek Chat API（流式） |
| Markdown | markdown-it + highlight.js + KaTeX + Mermaid |
| 工具库 | Vitest、Vue DevTools |

## 项目结构

```
src/
├── components/
│   ├── chat/            # 聊天核心组件
│   │   ├── AssistantMsg.vue   # AI 回复消息
│   │   ├── UserMsg.vue        # 用户消息
│   │   ├── ChatInput.vue      # 输入框
│   │   ├── FileUpload.vue     # 文件上传
│   │   ├── QuickQuestions.vue # 快捷问题
│   │   └── types.ts           # 消息类型定义
│   └── layout/          # 布局组件
│       ├── ConversationSidebar.vue  # 侧边栏
│       └── ConversationItem.vue      # 会话项
├── pages/
│   └── chat.vue         # 主聊天页面
├── stores/
│   ├── conversation.ts  # 会话管理 + 消息管理
│   └── llm.ts           # LLM API 调用
├── mock/
│   └── mock.md          # Mock 流式响应内容
└── utils/
    ├── markdown.ts      # Markdown 渲染
    ├── transform.ts     # 流式数据处理
    └── highlights.ts    # 代码高亮
```
## 在线 Demo

**https://chat-ai-fawn-nine.vercel.app/**

Demo 运行在 Mock 模式下，所有对话内容为本地模拟数据，无需配置任何 API Key。

## 快速开始

```sh
pnpm install
pnpm dev
```

## 配置

在项目根目录创建 `.env` 文件：

```env
VITE_DEEPSEEK_API_KEY=your_api_key_here
```

> **Mock 模式**：不配置 API Key 时，自动切换为本地 Mock 模式，模拟流式输出。

## 功能特性

- 多会话管理（创建、切换、删除、持久化）
- 文件上传与内容注入
- 流式 AI 回复（支持中断）
- Markdown 渲染（代码高亮、LaTeX 公式、Mermaid 图表）
- 本地数据持久化（localStorage）






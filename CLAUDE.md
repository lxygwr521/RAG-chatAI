# CLAUDE.md

本文件为 Claude Code（claude.ai/code）在此仓库中工作时提供指导。

## 项目概览

AI 知识库对话平台（类 ChatGPT 风格）。前端 Vue 3 + Vite + TypeScript，后端 Python + FastAPI + LangChain。支持 DeepSeek 模型的流式响应、对话管理、文件上传、Markdown 渲染，以及基于 ChromaDB 的 RAG（检索增强生成）知识库。

## 常用命令

### 前端

```bash
pnpm dev          # 启动开发服务器，端口 3000（/api 代理到 localhost:3001）
pnpm build        # 类型检查后构建生产包
pnpm preview      # 预览生产构建
pnpm type-check   # 运行 vue-tsc --noEmit
pnpm lint         # 同时运行 oxlint 和 eslint（自动修复）
```

### 后端

```bash
cd server
uvicorn app.main:app --port 3001 --reload    # 开发模式启动（热重载）
uvicorn app.main:app --port 3001             # 生产模式启动
```

暂无测试。

## 架构

### 前后端分层

```
浏览器 (Vue 3, :3000)
  ├── UI 组件、Markdown 渲染（保持不变）
  ├── Pinia Store（缓存层，localStorage 兜底）
  └── src/api/llm.ts → fetch('/api/chat')
        │ SSE (DeepSeek 兼容格式)
FastAPI (Python, :3001)
  ├── POST /api/chat          → httpx 代理 DeepSeek（流式 SSE）
  ├── /api/conversations/*     → SQLite 持久化 CRUD
  └── /api/knowledge/documents → 知识库文档管理（RAG Phase）
```

### 后端项目结构

```
server/
  .env                          # DEEPSEEK_API_KEY 等密钥（不提交）
  .env.example                  # 配置模板
  pyproject.toml                # Python 依赖
  app/
    main.py                     # FastAPI app, CORS, lifespan（建表 + 数据目录）
    config.py                   # pydantic-settings，全部配置从 .env 读取
    api/
      deps.py                   # get_db 依赖注入
      chat.py                   # POST /api/chat（SSE streaming）
      conversations.py          # CRUD /api/conversations
      knowledge.py              # CRUD /api/knowledge/documents
    core/
      database.py               # SQLAlchemy async engine + aiOSQLite
      sse.py                    # SSE 响应辅助（sse-starlette）
    models/
      conversation.py           # Conversation, Message ORM
      knowledge.py              # KnowledgeDocument, KnowledgeChunk ORM
    services/
      llm_service.py            # httpx 调 DeepSeek 流式 API + mock 模式
      context_service.py        # 上下文压缩（从 context.ts 移植，待实现）
      rag_service.py            # RAG 检索逻辑（待实现）
    rag/
      loader.py                 # 文档加载器
      splitter.py               # 中文优化分块策略
      embedder.py               # embedding 模型封装
      retriever.py              # ChromaDB 检索
      prompt.py                 # RAG prompt 模板
  data/                         # gitignored 运行时数据
    chat.db                     # SQLite 数据库
    chroma/                     # ChromaDB 向量持久化
    uploads/                    # 上传文档
```

### 数据库（SQLite）

- **conversations**: `id`, `title`, `model`, `created_at`, `updated_at`, `summary_text`, `summarized_count`
- **messages**: `id`, `conversation_id(FK)`, `role`, `content`, `thinking_content`, `files_json`, `citations_json`, `timestamp`
- **knowledge_documents**: `id`, `filename`, `file_path`, `file_type`, `file_size`, `chunk_count`, `status`, `created_at`
- **knowledge_chunks**: `id`, `document_id(FK)`, `chunk_index`, `content`, `metadata_json`, `chroma_id`

### 数据流（当前）

1. [chat.vue](src/pages/chat.vue) 处理用户输入 → 创建/更新会话 → 将 `UserMessage` 添加到 store → 调用 `buildLLMMessages()`。
2. `buildLLMMessages()` 将 store 消息转换为 `LLMMessage[]`，追加当前用户消息。
3. 消息数组通过 [src/api/llm.ts](src/api/llm.ts) 的 `callLLM()` 发送至 `POST /api/chat`。
4. 后端 [server/app/api/chat.py](server/app/api/chat.py) 接收请求 → 创建/更新会话 → 持久化用户消息 → 调用 `llm_service.deepseek_chat_stream()` → httpx 流式请求 DeepSeek API → 转发 SSE delta（保持 `{choices: [{delta: {content, reasoning_content}}]}` 格式）。
5. [chat.vue](src/pages/chat.vue) 读取 SSE 流，解析逻辑与之前完全一致：区分 `reasoning_content`（`<think>` 包裹）与 `content`，10 字符逐块追加到 `AssistantMessage`。
6. 流结束后，后端持久化完整 assistant 消息到 SQLite。

**上下文压缩**（已移至后端，待 Phase 2）：[src/utils/context/context.ts](src/utils/context/context.ts) 的逻辑将移植到 `server/app/services/context_service.py`（使用 `tiktoken` 精准计数）。当前暂时不压缩。

### 消息类型

定义在 [src/components/chat/types.ts](src/components/chat/types.ts)：
- `Message = UserMessage | AssistantMessage`
- `UserMessage`：`{ role: 'user', content, timestamp, files?: UploadFile[] }`
- `AssistantMessage`：`{ role: 'assistant', content, thinkingContent?, citations?, timestamp }`
- `Citation`：`{ document, snippet, score, chunk_id }` — RAG 引用来源
- 组件使用独立的 `UserMessageProps` / `AssistantMessageProps` 类型

### SSE 流处理

[src/utils/transform.ts](src/utils/transform.ts) 的 `TransformStream` **保持不变**：
1. 缓冲接收到的数据块。
2. 检测 SSE 格式（`data:` 前缀）或原始 JSON 格式。
3. 按 `\n` 分割，提取完整的 JSON 对象并入队供 reader 读取。

后端 [server/app/api/chat.py](server/app/api/chat.py) 使用 `sse-starlette` 的 `EventSourceResponse` 生成 SSE 流。SSE 数据格式与 DeepSeek 原始响应**完全兼容**（`{choices: [{delta: {content, reasoning_content}}]}`），因此前端解析器零改动。

Mock 模式已移至后端实现（`llm_service.mock_chat_stream()`），前端只发送 `model: "mock"`。

### Markdown 渲染

[src/utils/markdown.ts](src/utils/markdown.ts) 渲染助手回复：
- `transformThinkMarkdown()` — 将 `<think>...</think>` 内容包裹在 `<div class="think-wrapper">` 中，对 `<script>` 标签进行转义以防止 XSS 攻击。
- `transformMathMarkdown()` — 将 `\(` / `\[` LaTeX 分隔符转换为 `$` / `$$` 格式。
- 使用 `markdown-it` 配合 highlight.js（GitHub 主题）和 KaTeX 渲染数学公式。
- RAG 引用来源通过 [AssistantMsg.vue](src/components/chat/AssistantMsg.vue) 中的 `.assistant-msg-citations` 区块渲染。

### Vite 配置

- **路径别名**：`@` → `src/`
- **SCSS**：`_variables.scss` 通过 `additionalData` 自动注入到每个 SCSS `<style>` 块中，同时注入 `@use "sass:color"`。
- **自动导入**：Vue/Pinia API 以及 Naive UI 组合式函数均自动导入。Naive UI 组件自动解析。
- **开发代理**：`/api` → `http://localhost:3001`

### 核心依赖

**前端：**
- UI：Naive UI
- 样式：Tailwind CSS 4 + SCSS，设计 token 在 `_variables.scss`
- 状态：Pinia + `pinia-plugin-persistedstate`，localStorage 作为离线兜底
- Markdown：`markdown-it` + `highlight.js` + `katex`
- 代码检查：oxlint（主要）+ eslint（辅助）

**后端：**
- Web：FastAPI + uvicorn
- LLM：httpx（直调 DeepSeek API）
- 数据库：SQLAlchemy async + aiOSQLite
- SSE：sse-starlette
- RAG：LangChain + ChromaDB + OpenAI Embeddings（待 Phase 3）

## 运行时环境

- 前端：`.env` 中的 `VITE_DEEPSEEK_API_KEY` **已废弃**（API Key 移至 `server/.env`）
- 后端：`server/.env` 需要 `DEEPSEEK_API_KEY`，RAG Phase 还需要 `OPENAI_API_KEY`
- Node：`^20.19.0 || >=22.12.0`
- Python：`>=3.11`

## TypeScript 规则（来自 .cursor/rules）

- 业务类型写在 `.ts` 文件中，不要写在 `.d.ts` 中。
- `.d.ts` 仅用于全局声明（`declare global`）、第三方类型补充以及环境变量声明。
- Vue props 必须显式类型化。
- **不要删除任何注释。**

# CLAUDE.md

本文件为 Claude Code（claude.ai/code）在此仓库中工作时提供指导。

## 项目概览

AI 知识库对话平台。前端 Vue 3 + Vite + TypeScript，后端 Python + FastAPI + LangChain。支持 DeepSeek 流式对话、会话管理、文件上传、Markdown 渲染，以及基于 ChromaDB + ZhipuAI embeddings 的 RAG（检索增强生成）知识库。Agent 基于 LangGraph `create_agent`，工具调用和上下文压缩由 LangChain 原生 Middleware 处理。

## 常用命令

### 前端 (`frontend/`)

```bash
cd frontend
pnpm dev          # 启动开发服务器，端口 3000（/api 代理到 localhost:3001）
pnpm build        # 类型检查后构建生产包
pnpm type-check   # 运行 vue-tsc --noEmit
pnpm lint         # oxlint + eslint 自动修复
```

### 后端 (`server/`)

```bash
cd server
uvicorn app.main:app --port 3001 --reload    # 开发模式（热重载）
uvicorn app.main:app --port 3001             # 生产模式
```

## 架构

### 前后端分层

```
浏览器 (Vue 3, :3000)
  ├── UI 组件、Markdown 渲染
  ├── Pinia Store（内存缓存，启动时从后端加载）
  └── fetch('/api/chat') + '/api/conversations' + '/api/knowledge'
        │ SSE typed events (delta / citations / tool_call / tool_result / done)
FastAPI (Python, :3001)
  ├── POST /api/chat          → AgentService (LangGraph) → ChatOpenAI (DeepSeek) → SSE
  ├── /api/conversations/*     → SQLite CRUD
  └── /api/knowledge/documents → 知识库文档管理 (ZhipuAI embedding + ChromaDB)
```

### 后端项目结构

```
server/
  .env                          # DEEPSEEK_API_KEY, ZHIPUAI_API_KEY
  .env.example
  pyproject.toml
  app/
    main.py                     # FastAPI app, CORS, 请求日志, 全局异常处理
    config.py                   # pydantic-settings (DeepSeek + ZhipuAI + OpenAI)
    api/
      deps.py                   # get_db 依赖注入
      chat.py                   # POST /api/chat — 核心: 消息持久化 → Agent → SSE
      conversations.py          # CRUD /api/conversations + /messages
      knowledge.py              # CRUD /api/knowledge/documents
    core/
      database.py               # SQLAlchemy async + aiOSQLite + 性能索引
      sse.py                    # SSE 类型化事件 (SSEEvent)
    models/
      conversation.py           # Conversation, Message ORM
      knowledge.py              # KnowledgeDocument, KnowledgeChunk ORM
    schemas/
      chat.py                   # Pydantic: ChatRequest, ConversationOut, MessageOut
    services/
      llm_service.py            # 持久化辅助函数 (MessageModel 工厂)
      rag_service.py            # RAG 编排: ingest → augment → delete
      agent_service.py          # AgentService: LangGraph create_agent + SummarizationMiddleware
    tools/
      search_knowledge.py       # RAG 检索封装为 LangChain @tool
    rag/
      loader.py                 # 文档加载 (txt/md/pdf/csv/json 等)
      splitter.py               # 中文分块 (500 字符, 10% 重叠)
      embedder.py               # ZhipuAI → OpenAI → ONNX 三级 fallback
      retriever.py              # ChromaDB 检索 (阈值 1.5, top-k=5)
      prompt.py                 # RAG prompt 模板 + citations
  data/                         # gitignored
    chat.db                     # SQLite
    chroma/                     # ChromaDB 向量持久化
    uploads/                    # 上传文档原始文件
```

### 数据流（完整）

```
POST /api/chat
  │
  ├─ ① 会话: 查找/创建 Conversation → SQLite
  ├─ ② 持久化: UserMessage → SQLite
  ├─ ③ 过滤: 去除前端通用 system message (Agent 有自己的 SYSTEM_PROMPT)
  ├─ ④ Agent: agent_service.run(llm_messages)
  │     ├─ SummarizationMiddleware.before_model  → token > 60K 或消息 > 80 条时自动压缩
  │     │   旧消息 → DeepSeek flash 摘要, 保留最近 20 条原样
  │     ├─ Agent 自主决定是否调用 search_knowledge 工具检索知识库
  │     └─ ChatOpenAI (DeepSeek) → SSE delta/tool_call/tool_result 事件
  ├─ ⑤ 持久化: AssistantMessage → SQLite
  └─ ⑥ 响应: SSE 事件流返回前端
```

### 上下文压缩（SummarizationMiddleware）

基于 `langchain.agents.middleware.summarization.SummarizationMiddleware`，替代了旧的自定义 `context_service.py`：

- **触发条件**: token > 60,000 或消息 > 80 条（OR，任一满足）
- **保留策略**: 最近 20 条消息保持原样
- **摘要模型**: `deepseek-v4-flash`（轻量快速）
- **保护机制**: 不会切断 AI/Tool 消息对（tool_call + tool_result 始终在一起）
- **SYSTEM_PROMPT**: 存储于 `ModelRequest.system_message`，Middleware 的 `RemoveMessage(REMOVE_ALL_MESSAGES)` 只清除 `state["messages"]`，不影响 system prompt

### 数据库 (SQLite)

| 表 | 关键列 | 索引 |
|------|------|------|
| conversations | id, title, model, summary_text, summarized_count | updated_at |
| messages | id, conversation_id(FK), role, content, thinking_content, citations_json | conversation_id, timestamp, role |
| knowledge_documents | id, filename, file_path, status, chunk_count | created_at |
| knowledge_chunks | id, document_id(FK), content, chroma_id | document_id |

> `summary_text` / `summarized_count` 列保留但不再更新——SummarizationMiddleware 每次请求独立判断压缩，无需持久化摘要。

### SSE 事件类型

前端 `transform.ts` 解析 `event:` 行, `chat.vue` 按类型分发:

| event | data | 前端处理 |
|------|------|---------|
| `delta` | `{"choices":[{"delta":{"content":"..."}}]}` | 逐字追加到 AssistantMessage |
| `citations` | `{"citations":[{document,snippet,score}]}` | 存入助理消息, AssistantMsg 渲染引用 |
| `tool_call` | `{"tool_call_id","tool_name","arguments"}` | ToolCallBanner 展示 |
| `tool_result` | `{"tool_call_id","result","success"}` | ToolCallBanner 更新状态 |
| `done` | `[DONE]` | 结束流 |

### 嵌入模型优先级

```
ZhipuAI embedding-2 (ZHIPUAI_API_KEY) → OpenAI text-embedding-3-small → ONNX 本地
```

### 存储职责

| 存储 | 内容 |
|------|------|
| SQLite | 会话、消息、文档元数据、chunk 索引 |
| ChromaDB | 向量 + 原文副本 + metadata (相似度检索) |
| data/uploads/ | 上传原始文件 |
| Pinia (内存) | 前端工作缓存, 启动时从后端加载 |

## 前端约束

- 无 RAG 按钮（所有对话统一走 Agent 链路，Agent 自主决定是否检索知识库）
- 无 `SYSTEM_MESSAGE`（Agent 有自己的 SYSTEM_PROMPT，前端 system message 被后端过滤）
- 无 `use_rag` 参数（ChatRequest 中已移除）
- ChatInput 只发送 `{model, messages, conversation_id?, files?}`

## 核心依赖

**前端**: Vue 3, Pinia, Naive UI, Tailwind CSS 4, SCSS, markdown-it + highlight.js + katex

**后端**: FastAPI, uvicorn, SQLAlchemy async + aiOSQLite, sse-starlette, chromadb, langchain (agents + middleware), langchain-openai, langchain-core, langchain-text-splitters, langchain-classic (SummarizerMixin), openai (调 ZhipuAI/OpenAI), pypdf, pydantic-settings

## 运行时环境

- **前端**: `frontend/.env` 无需配置（API Key 全在后端）
- **后端**: `server/.env` 需要 `DEEPSEEK_API_KEY` + `ZHIPUAI_API_KEY`
- Node: `^20.19.0 || >=22.12.0`
- Python: `>=3.11`

## TypeScript 规则（来自 .cursor/rules）

- 业务类型写在 `.ts` 文件中，不要写在 `.d.ts` 中。
- `.d.ts` 仅用于全局声明、第三方类型补充、环境变量声明。
- Vue props 必须显式类型化。
- **不要删除任何注释。**

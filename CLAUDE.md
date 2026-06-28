# CLAUDE.md

本文件为 Claude Code（claude.ai/code）在此仓库中工作时提供指导。

## 项目概览

AI 知识库对话平台。前端 Vue 3 + Vite + TypeScript，后端 Python + FastAPI。支持 DeepSeek 流式对话、会话管理、文件上传、Markdown 渲染，以及基于 ChromaDB + ZhipuAI embeddings 的 RAG（检索增强生成）知识库。

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
        │ SSE typed events (delta / citations / done)
FastAPI (Python, :3001)
  ├── POST /api/chat          → 上下文压缩 → RAG 检索 → AgentService → DeepSeek
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
      chat.py                   # POST /api/chat — 核心: context压缩→RAG→LLM→SSE
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
      llm_provider.py           # LLMProvider 抽象 (DeepSeekProvider / MockProvider)
      llm_service.py            # 持久化辅助函数
      context_service.py        # 上下文压缩 (tiktoken, 80K 阈值, 20 窗口)
      rag_service.py            # RAG 编排: ingest → augment → delete
      agent_service.py          # AgentService (Phase 5: ReAct loop)
      tool_registry.py          # Tool 注册/查询
    tools/
      base.py                   # BaseTool 基类
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
  ├─ ③ 上下文压缩: context_service.build_context()
  │     超 80K token → DeepSeek 摘要 → 存 summary_text
  ├─ ④ RAG (use_rag=true): rag_service.augment_chat()
  │     query → ZhipuAI embed → ChromaDB top-5 → 注入 system prompt
  ├─ ⑤ LLM: agent_service.run() → httpx DeepSeek → SSE delta events
  ├─ ⑥ Citations: yield SSEEvent("citations", [...])
  └─ ⑦ 持久化: AssistantMessage → SQLite
```

### 数据库 (SQLite)

| 表 | 关键列 | 索引 |
|------|------|------|
| conversations | id, title, model, summary_text, summarized_count | updated_at |
| messages | id, conversation_id(FK), role, content, thinking_content, citations_json | conversation_id, timestamp, role |
| knowledge_documents | id, filename, file_path, status, chunk_count | created_at |
| knowledge_chunks | id, document_id(FK), content, chroma_id | document_id |

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

## 核心依赖

**前端**: Vue 3, Pinia, Naive UI, Tailwind CSS 4, SCSS, markdown-it + highlight.js + katex

**后端**: FastAPI, uvicorn, httpx, SQLAlchemy async + aiOSQLite, sse-starlette, chromadb, langchain, langchain-text-splitters, openai (调 ZhipuAI/OpenAI), tiktoken, pypdf, pydantic-settings

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

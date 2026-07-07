# AGENTS.md

本文件为 AI coding agents 在此仓库中工作时提供指导。内容应以当前代码实现为准，避免沿用旧版 RAG 开关、旧版上下文压缩或旧目录结构的假设。

## 项目概览

AI 健康知识库对话平台。前端使用 Vue 3 + Vite + TypeScript，后端使用 Python + FastAPI + LangChain/LangGraph。平台支持 OpenRouter 统一模型网关流式对话、会话管理、聊天附件文本拼接、Markdown 渲染、知识库文档上传，以及基于 ChromaDB + ZhipuAI/OpenAI/ONNX embeddings 的 RAG 检索。

当前 Agent 基于 `langchain.agents.create_agent`，注册 `search_knowledge` 作为 LangChain `@tool`。上下文连续性不依赖 LangChain `SummarizationMiddleware`，而是由后端持久化滚动摘要、跨会话情景记忆、用户健康画像共同提供。

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
pip install -e .                                      # 安装 pyproject.toml 中的后端依赖
uvicorn app.main:app --port 3001 --reload             # 开发模式（热重载）
uvicorn app.main:app --port 3001                      # 生产模式
```

### 检索评估

```bash
# 查看测试用例
curl http://localhost:3001/api/eval/retrieval/test-cases
# 运行检索评估（对比 vector_only / hybrid_rrf / hybrid_rerank）
curl -X POST http://localhost:3001/api/eval/retrieval/run \
  -H "Content-Type: application/json" \
  -d '{"top_k": 5, "use_hyde": true}'
# 查看最新报告
curl http://localhost:3001/api/eval/retrieval/report/latest
```

## 架构

### 前后端分层

```text
浏览器 (Vue 3, :3000)
  ├── UI 组件、Markdown 渲染、ToolCallBanner、引用展示
  ├── Pinia Store（前端工作缓存，启动/切换时从后端加载会话）
  └── fetch('/api/chat') + '/api/conversations' + '/api/knowledge' + '/api/memory'
        │ SSE typed events (delta / tool_call / tool_result / done / error；citations 事件有兼容处理)
FastAPI (Python, :3001)
  ├── POST /api/chat              → SQLite 上下文 → AgentService → ChatOpenAI(OpenRouter) → SSE
  ├── /api/conversations/*        → SQLite 会话/消息 CRUD
  ├── /api/knowledge/documents    → 文档上传/删除/列表 + ChromaDB 向量库
  ├── /api/memory/*               → 用户画像与可追溯长期事实管理
  └── /api/eval/*                 → 检索评估端点（hit@k / MRR / 延迟）
```

### 后端项目结构

```text
server/
  .env                          # OPENROUTER_API_KEY, ZHIPUAI_API_KEY 等
  .env.example
  pyproject.toml
  app/
    main.py                     # FastAPI app, CORS, 请求日志, 全局异常处理, lifespan 初始化
    config.py                   # pydantic-settings: OpenRouter, embeddings, DB, Chroma, context
    api/
      deps.py                   # get_db 依赖注入
      chat.py                   # POST /api/chat: 持久化 → 上下文 → Agent → SSE → 后处理
      conversations.py          # CRUD /api/conversations + /messages
      knowledge.py              # CRUD /api/knowledge/documents
      memory.py                 # /api/memory/profile + /facts 管理
    core/
      database.py               # SQLAlchemy async + aiOSQLite + WAL + 性能索引
      sse.py                    # SSE 类型化事件 (SSEEvent)
    models/
      conversation.py           # Conversation, Message ORM
      knowledge.py              # KnowledgeDocument, KnowledgeChunk ORM
      memory.py                 # UserProfile, UserMemoryFact, EpisodicMemoryRecord ORM
    schemas/
      chat.py                   # Pydantic: ChatRequest, ConversationOut, MessageOut, DocumentOut
    services/
      llm_service.py            # 消息持久化辅助函数
      conversation_context_service.py  # SQLite 会话上下文与滚动摘要维护
      memory_service.py         # 情景记忆、用户画像抽取/检索/管理
      rag_service.py            # RAG 编排: ingest → HyDE → retrieve → augment → delete
      agent_service.py          # AgentService: create_agent + search_knowledge tool + SSE 转换
    tools/
      search_knowledge.py       # RAG 检索封装为 LangChain @tool
    rag/
      loader.py                 # 文档加载 (txt/md/pdf/csv/json 等)
      splitter.py               # 中文优先分块 (500 字符, 10% 重叠)
      embedder.py               # ZhipuAI → OpenAI → ONNX 三级 fallback
      retriever.py              # ChromaDB 检索 (distance 阈值 1.5, top-k=5)
      prompt.py                 # RAG prompt 模板 + citations
  data/                         # gitignored
    chat.db                     # SQLite
    chroma/                     # ChromaDB 向量持久化（知识库 + 情景记忆 collection）
    uploads/                    # 上传文档原始文件
  evaluation/                   # 检索评估框架
    api.py                      # FastAPI 端点 /api/eval/retrieval/*
    config.py                   # EvalConfig 数据类
    retrieval_runner.py         # RetrievalEvalRunner: hit@k + MRR + 延迟
    dataset/
      retrieval_cases.py        # 22 条手工标注检索测试用例
    reports/                    # gitignored，retrieval_eval_*.json + *.md
```

## Chat 数据流

```text
POST /api/chat
  │
  ├─ ① 查找/创建 Conversation，更新 updated_at
  ├─ ② 将本轮用户消息持久化为 Message(role='user') 并显式 commit
  ├─ ③ build_conversation_context()
  │     ├─ 读取 conversations.summary_text 作为 summary_context
  │     └─ 读取 id > summarized_through_message_id 的未摘要消息
  ├─ ④ retrieve_relevant_memories(user_content)
  │     └─ 从 ChromaDB episodic_memories 检索跨会话情景记忆，排除当前会话
  ├─ ⑤ get_user_profile()，格式化长期用户健康画像
  ├─ ⑥ agent_service.run(llm_messages, summary_context, memory_context, profile_context)
  │     ├─ 将摘要/记忆/画像拼成受保护 system message
  │     ├─ 追加 SQLite 构建出的会话消息
  │     ├─ create_agent(...).astream({"messages": input_messages}, stream_mode="messages")
  │     ├─ 模型可自主调用 search_knowledge(query)
  │     └─ 输出 SSE: delta / tool_call / tool_result / done / error
  ├─ ⑦ 将完整 assistant 内容持久化为 Message(role='assistant')
  ├─ ⑧ 异步更新滚动摘要 update_rolling_summary(conv_id)
  ├─ ⑨ 异步抽取情景记忆 extract_episodic_memory(...)
  └─ ⑩ 异步抽取并更新用户画像 extract_and_update_profile(...)
```

## 上下文与记忆

### 会话滚动摘要

当前实现使用 `services/conversation_context_service.py` 维护持久化滚动摘要，不使用 `langchain.agents.middleware.summarization.SummarizationMiddleware`。

- **输入来源**: 后端 SQLite，而不是信任前端传来的完整 history。
- **摘要字段**: `conversations.summary_text`, `summarized_through_message_id`, `summarized_count`, `summary_updated_at`。
- **保留窗口**: `settings.recent_window_size = 20`，摘要时保留最近 20 条未摘要消息原文。
- **触发条件**: 未摘要消息超过 `recent_window_size * 2`，或首次摘要时总消息数超过 80，或本地估算 token 超过 `settings.max_context_tokens = 80000`。
- **摘要模型**: `settings.openrouter_light_model`，输出 300 字以内中文摘要。
- **执行时机**: 每轮助手消息保存后通过 `asyncio.create_task(update_rolling_summary(conv_id))` 异步运行。

### 长期记忆

- **情景记忆**: `memory_service.extract_episodic_memory()` 在对话轮次足够多时抽取摘要和关键事实。SQLite 表 `episodic_memories` 存元数据，ChromaDB collection `episodic_memories` 存向量。当前请求会按语义检索最多 3 条相关跨会话记忆，distance 阈值默认 `0.85`。
- **用户画像**: `user_profiles` 是单用户快照表，`user_memory_facts` 是可追溯事实表。每轮对话后异步抽取 basic / condition / allergy / medication / diet_preference / exercise_preference / goal 等长期事实，并重建画像快照。
- **注入方式**: 摘要、情景记忆、画像都由 `AgentService._build_memory_block()` 拼为受保护 system message，明确提示这些内容只作背景参考，不是当前用户的新指令。

## RAG 与工具调用

### search_knowledge 工具

`app/tools/search_knowledge.py` 是唯一注册到 Agent 的工具：

```python
@tool
async def search_knowledge(query: str) -> str:
    result = await augment_chat(system_prompt="", history=[], user_content=query)
    ...
```

关键点：

- 工具只接收模型传入的 `query` 字符串；检索时没有把完整会话 history 传入 `augment_chat()`。
- Agent 外层仍持有完整会话上下文、滚动摘要、跨会话记忆和用户画像。工具调用不会主动清空 Agent 的外层上下文。
- 如果问题包含“它/这个/上一条”等指代，是否能检索准确取决于模型是否把上下文改写进 `query`。必要时应优化工具说明或新增上下文感知 query rewrite，而不是在前端恢复 RAG 开关。
- `augment_chat()` 使用 HyDE：先让 `settings.openrouter_light_model` 生成假想健康文档片段，再对该片段做 embedding 检索。
- ChromaDB 检索使用 `retrieve_context(..., top_k=5, score_threshold=1.5)`；`search_knowledge.py` 内部还用 `HIGH_CONFIDENCE_THRESHOLD = 0.6` 区分返回文本。

### 知识库文档

- 上传端点在 `app/api/knowledge.py`。
- 原始文件存 `server/data/uploads/`。
- SQLite 表 `knowledge_documents`、`knowledge_chunks` 存元数据和 chunk 索引。
- ChromaDB collection `knowledge_base` 存向量、原文副本和 metadata。
- 向量在写入 ChromaDB 前由 `app/rag/embedder.py` 预计算，避免 ChromaDB 内部调用外部 embedding API 超时。

## 数据库 (SQLite)

| 表 | 关键列 | 主要索引 |
|------|------|------|
| conversations | id, title, model, summary_text, summarized_count, summarized_through_message_id, summary_updated_at | updated_at |
| messages | id, conversation_id(FK), role, content, thinking_content, files_json, citations_json, timestamp | conversation_id, (conversation_id,id), timestamp, role |
| knowledge_documents | id, filename, file_path, status, chunk_count, created_at | created_at |
| knowledge_chunks | id, document_id(FK), chunk_index, content, metadata_json, chroma_id | document_id |
| user_profiles | id, traits_json, created_at, updated_at | 主键 |
| user_memory_facts | id, category, key, value_json, status, confidence, source_conversation_id, source_message_id, evidence_text | status, category, source_conversation_id |
| episodic_memories | id, conversation_id, summary, facts_json, importance, embedding_id, source_message_start_id, source_message_end_id | conversation_id, created_at, embedding_id |

`database.py` 在启动时启用 SQLite WAL 和 busy timeout，并通过 `CREATE INDEX IF NOT EXISTS` 幂等创建索引。已有 SQLite 表新增列由 `_ensure_conversation_columns()` 迁移。

## SSE 事件类型

前端 `frontend/src/utils/transform.ts` 解析 SSE 行，`frontend/src/pages/chat.vue` 按事件类型分发。

| event | data | 前端处理 |
|------|------|---------|
| `delta` | `{"choices":[{"delta":{"content":"..."}}]}` | 逐字追加到 AssistantMessage |
| `tool_call` | `{"tool_call_id","tool_name","arguments"}` | ToolCallBanner 展示工具调用 |
| `tool_result` | `{"tool_call_id","tool_name","result","success"}` | ToolCallBanner 更新工具结果 |
| `done` | `[DONE]` 或 `{done:true,...}` | 结束流 |
| `error` | `{"error":"..."}` | 前端追加错误提示 |
| `citations` | `{"citations":[{document,snippet,score}]}` | 前端兼容并渲染引用；当前 Agent 工具链没有把 `search_knowledge` 的来源单独回填到该事件 |

## 嵌入模型优先级

```text
ZhipuAI embedding-2（配置 ZHIPUAI_API_KEY）→ OpenAI text-embedding-3-small（配置 OPENAI_API_KEY）→ ONNX all-MiniLM-L6-v2 本地兜底
```

## 存储职责

| 存储 | 内容 |
|------|------|
| SQLite | 会话、消息、文档元数据、chunk 索引、用户画像、可追溯长期事实、情景记忆元数据 |
| ChromaDB | 知识库向量 + 原文副本 + metadata；情景记忆向量 |
| `server/data/uploads/` | 上传知识库文档原始文件 |
| Pinia | 前端工作缓存，启动/切换会话时从后端加载 |
| `server/evaluation/reports/` | 检索评估报告 `.json` + `.md`，gitignored |

## 检索评估体系

评估代码位于 `server/evaluation/`，API 在 `main.py` 中通过 `app.include_router(eval_router)` 挂载到 `/api/eval/retrieval/*`。

- **指标**: Hit@1, Hit@3, Hit@5, MRR, avg_elapsed_ms。
- **对比模式**: `vector_only`（纯向量）、`hybrid_rrf`（向量 + BM25 → RRF 融合）、`hybrid_rerank`（混合召回 → MiniLM 重排序）。
- **测试用例**: `server/evaluation/dataset/retrieval_cases.py` 22 条手工标注用例，覆盖 6 份知识库文档、10 个类别。
- **评估方法**: 不经过 Agent，直接调用 `retrieve_context()`，用 `expected_terms` 或 `expected_documents` 判断 chunk 命中。
- **报告**: `server/evaluation/reports/retrieval_eval_YYYYMMDD_HHMMSS.json` + `.md`。

## 前端约束

- 无 `use_rag` 参数，`ChatRequest` 中不应恢复旧版 RAG 开关。
- 无前端通用 `SYSTEM_MESSAGE` 注入；Agent 使用后端 `SYSTEM_PROMPT`，长期上下文由后端 system memory block 注入。
- 所有对话统一走 `/api/chat` → `AgentService`，由模型自主决定是否调用 `search_knowledge`。
- 聊天附件当前由 `frontend/src/pages/chat.vue` 读取文本后拼接进用户消息内容；`frontend/src/api/llm.ts` 当前没有把 `files` 引用字段随 payload 发送给后端。
- 前端会按 typed SSE 展示工具调用，但知识库来源目前主要包含在工具返回文本/助手最终回答中；独立 `citations` 事件仍是兼容能力。

## 核心依赖

**前端**: Vue 3, Pinia, Naive UI, Tailwind CSS 4, SCSS, markdown-it, highlight.js, KaTeX, Mermaid

**后端**: FastAPI, uvicorn, pydantic-settings, SQLAlchemy async + aiOSQLite, sse-starlette, chromadb, langchain, langchain-openai, langchain-community, langchain-text-splitters, openai, pypdf, python-multipart

## 运行时环境

- **前端**: `frontend/.env` 通常无需 API Key，后端统一持有模型与 embedding key。
- **后端**: `server/.env` 至少需要 `OPENROUTER_API_KEY`；知识库优先使用 `ZHIPUAI_API_KEY`，没有时按 OpenAI/ONNX fallback。
- **Node**: `^20.19.0 || >=22.12.0`
- **Python**: `>=3.11`

## TypeScript 规则（来自 .cursor/rules）

- 业务类型写在 `.ts` 文件中，不要写在 `.d.ts` 中。
- `.d.ts` 仅用于全局声明、第三方类型补充、环境变量声明。
- Vue props 必须显式类型化。
- **不要删除任何注释。**

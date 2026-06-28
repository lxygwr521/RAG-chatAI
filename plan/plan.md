# Plan: AI Chat → 知识库 RAG 平台重构

## 背景

当前项目是纯前端 AI 聊天应用（Vue 3 + Vite + TypeScript），直接调用 DeepSeek API。存在三个核心问题：

1. **API Key 暴露** — `VITE_DEEPSEEK_API_KEY` 打包到浏览器 JS 中
2. **无持久化后端** — 所有数据仅存 `localStorage`，无法做知识库检索
3. **上下文压缩在前端** — 浏览器端额外调用 DeepSeek API 做摘要，浪费且不安全

目标：引入 Python + FastAPI + LangChain 后端，将项目重构为支持 RAG 的知识库对话平台。前端改动最小化（SSE 协议兼容），后端渐进式替代。

---

## 目标架构

```
浏览器 (Vue 3, port 3000)
  ├── 保留: UI 组件、Markdown 渲染、Pinia Store (缓存层)
  ├── 改动: src/api/llm.ts → 调 /api/chat (不再直连 DeepSeek)
  └── 新增: 知识库管理面板、RAG 开关、引用展示
        │ SSE (TransformStream 不变)
FastAPI (Python, port 3001)
  ├── POST /api/chat          → httpx 代理 DeepSeek (流式 SSE)
  ├── /api/conversations/*     → CRUD (SQLite 持久化)
  ├── /api/knowledge/documents → 知识库文档管理
  └── RAG Pipeline:
      文档加载 → 中文友好分块 → text-embedding-3-small 向量化
      → ChromaDB 存储 → 相似度检索 → 增强 Prompt → LLM 回答
```

---

## 后端项目结构

> ✅ = 已实现 (Phase 0+1) &nbsp; ⏳ = 待实现 (Phase 2) &nbsp; 🔜 = 待实现 (Phase 3)

```
server/
  pyproject.toml                ✅
  .env                          ✅ DEEPSEEK_API_KEY, OPENAI_API_KEY
  .env.example                  ✅ 配置模板
  app/
    main.py                     ✅ FastAPI app, CORS, lifespan
    config.py                   ✅ pydantic-settings, 全部配置从 .env 读取
    api/
      __init__.py               ✅
      deps.py                   ✅ get_db 依赖注入 (session commit/rollback)
      chat.py                   ✅ POST /api/chat (SSE, mock + DeepSeek 代理)
      conversations.py          ✅ CRUD /api/conversations + messages
      knowledge.py              🔜 CRUD /api/knowledge/documents
    core/
      __init__.py               ✅
      database.py               ✅ SQLAlchemy async engine + aiOSQLite
      sse.py                    ✅ SSE 辅助 (sse-starlette EventSourceResponse)
    models/
      __init__.py               ✅
      conversation.py           ✅ Conversation, Message ORM
      knowledge.py              ✅ KnowledgeDocument, KnowledgeChunk ORM
    schemas/
      __init__.py               ✅
      chat.py                   ✅ ChatRequest, ConversationCreate/Out, MessageOut, DocumentOut
    services/
      __init__.py               ✅
      llm_provider.py           ⏳ LLM Provider 抽象 (DeepSeek / Mock)
      llm_service.py            ✅ httpx 调 DeepSeek 流式 → 重构为 DeepSeekProvider
      context_service.py        ⏳ 上下文压缩 (tiktoken 精准计数)
      rag_service.py            🔜 RAG 检索 + Prompt 构建
      agent_service.py          ⏳ Agent Loop 骨架 (占位，Phase 3 实现 ReAct)
      tool_registry.py          ⏳ Tool 注册/查询
    tools/
      __init__.py               ⏳
      base.py                   ⏳ BaseTool 基类 (name, description, parameters, execute)
      search_knowledge.py       🔜 SearchKnowledgeTool — RAG 检索为 Tool
    rag/
      __init__.py               ✅
      loader.py                 🔜 文档加载 (txt/md/pdf/csv/json)
      splitter.py               🔜 中文优化分块 (RecursiveCharacterTextSplitter)
      embedder.py               🔜 OpenAIEmbeddings 封装, 可替换 Provider
      retriever.py              🔜 ChromaDB similarity_search, 分数阈值过滤
      prompt.py                 🔜 RAG prompt 模板
  data/                         ✅ gitignored
    chat.db                     ✅ SQLite (自动创建)
    chroma/                     🔜 ChromaDB 持久化目录
    uploads/                    🔜 上传文档存储
```

**依赖**: `fastapi`, `uvicorn`, `sqlalchemy[asyncio]`, `aiosqlite`, `httpx`, `sse-starlette`, `langchain`, `langchain-community`, `langchain-text-splitters`, `langchain-openai`, `chromadb`, `pydantic-settings`, `tiktoken`, `python-multipart`, `pypdf`

---

## API 设计

### POST /api/chat (核心)

**请求**:
```json
{
  "conversation_id": "uuid-or-null",
  "model": "deepseek | deepseek-think | mock",
  "messages": [{"role": "system/user/assistant", "content": "..."}],
  "use_rag": true,
  "files": [{"id": "file-id", "filename": "doc.txt"}]
}
```

**响应**: SSE 流 (`text/event-stream`)，**保持 DeepSeek 原始 delta 格式以兼容前端解析器**:

```
data: {"choices":[{"delta":{"reasoning_content":"Let me think..."}}]}

data: {"choices":[{"delta":{"content":"RAG stands for"}}]}

data: {"choices":[{"delta":{"content":" Retrieval-Augmented Generation."}}]}

data: {"citations":[{"document":"notes.txt","snippet":"RAG is a...","score":0.92}]}

data: [DONE]
```

> **关键决策**: `{choices: [{delta: {content, reasoning_content}}]}` 格式与 [chat.vue:251-252](src/pages/chat.vue#L251-L252) 现有解析逻辑**完全兼容**，前端 SSE 读取循环零改动。`citations` 是新增字段，前端可选处理。

### 会话 CRUD

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/conversations` | 列表 (含 message_count) |
| POST | `/api/conversations` | 创建 `{title, model}` |
| DELETE | `/api/conversations/:id` | 删除 (级联删消息) |
| GET | `/api/conversations/:id/messages` | 消息列表 `?offset=0&limit=50` |

### 知识库 CRUD

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/knowledge/documents` | multipart 上传 (支持多文件) |
| GET | `/api/knowledge/documents` | 文档列表 |
| DELETE | `/api/knowledge/documents/:id` | 删除 (级联删 chunks + 向量) |

---

## 数据库设计 (SQLite)

### conversations
`id (TEXT PK)`, `title`, `model`, `created_at`, `updated_at`, `summary_text (nullable)`, `summarized_count (INT DEFAULT 0)`

### messages
`id (INTEGER PK)`, `conversation_id (FK→conversations)`, `role`, `content`, `thinking_content (nullable)`, `files_json (nullable)`, `citations_json (nullable)`, `timestamp`

### knowledge_documents
`id (TEXT PK)`, `filename`, `file_path`, `file_type`, `file_size`, `chunk_count`, `status (processing/ready/error)`, `created_at`

### knowledge_chunks
`id (TEXT PK)`, `document_id (FK→knowledge_documents)`, `chunk_index`, `content`, `metadata_json (nullable)`, `chroma_id` (对应 ChromaDB document ID)

> 向量数据仅存 ChromaDB (`data/chroma/`)，`knowledge_chunks` 是关系索引。

---

## RAG 管道设计

### 分块策略
使用 LangChain `RecursiveCharacterTextSplitter`，中文优先分隔符：

```
chunk_size=500 字符  (~300 tokens for Chinese)
chunk_overlap=50 字符 (10%)
separators: ["\n\n", "\n", "。", "！", "？", "；", "，", ".", "!", "?", " "]
```

### 嵌入模型
**默认**: OpenAI `text-embedding-3-small` (dimensions=1024)，中文效果好，无需本地 GPU。

**可替换**: 通过 `embedder.py` 抽象接口，后续可切 `BAAI/bge-large-zh-v1.5` 或其他本地模型。

### 检索逻辑
```
query → embed → ChromaDB similarity_search_with_score(k=5)
  → score 过滤 (<0.3 视为不相关)
  → 格式化注入 system prompt
```

### 决策逻辑
当 `use_rag=true` 且知识库有文档时启用 RAG。后续可升级为后端自动判断。

---

## 前端改动清单

> ✅ = 已完成 (Phase 1) &nbsp; 🔜 = 待实现 (Phase 3-4)

### 需要改的文件

| 文件 | 改动程度 | 状态 | 说明 |
|------|---------|------|------|
| `src/api/llm.ts` | **重写** | ✅ | 去掉 DeepSeek 直连, 改为 `fetch('/api/chat')`; 删除 `readFiles()`, `buildUserContent()`, API key 用法 |
| `src/pages/chat.vue` | **中** | ✅ | 简化 `buildLLMMessages` (不再调 `buildContext`); 干掉 `simulateMockResponse`; SSE 循环增加 `citations` 处理; mock 模式由后端接管 |
| `src/components/chat/types.ts` | **小** | ✅ | 新增 `Citation` 接口; `AssistantMessage` 加 `citations?` 字段 |
| `src/components/chat/AssistantMsg.vue` | **小** | ✅ | 新增 RAG 引用来源展示区块 (`.assistant-msg-citations`) |
| `src/stores/conversation.ts` | **中** | 🔜 | 增加后端同步; `summaryMap` 不再做上下文压缩的 source of truth |
| `src/components/chat/ChatInput.vue` | **小** | 🔜 | 新增 RAG toggle 按钮; 文件上传改为先上传后端拿 ID |

### 新增文件

| 文件 | 状态 | 说明 |
|------|------|------|
| `src/api/conversation.ts` | ✅ | 会话后端 CRUD 客户端 |
| `src/api/knowledge.ts` | 🔜 | 知识库文档 CRUD 客户端 |
| `src/components/knowledge/KnowledgePanel.vue` | 🔜 | 知识库管理面板 (上传/列表/删除) |

### 保持不变的文件
`src/utils/transform.ts`, `src/utils/markdown.ts`, `src/utils/highlights.ts`, `src/utils/preWrapper.ts`, `src/components/chat/UserMsg.vue`, `src/components/chat/ChatNav.vue`, `src/hooks/useCopyCode.ts`, `src/styles/_variables.scss`, `src/styles/markdown.css`, `vite.config.ts` (proxy 已配置好)

### 可删除的文件 (分阶段)
- `src/mock/index.ts` + `src/mock/mock.md` — mock 模式移到后端
- `src/utils/context/context.ts` + `src/utils/context/token.ts` — 上下文压缩移到后端
- `.env` 中的 `VITE_DEEPSEEK_API_KEY` — 密钥移到 `server/.env`

---

## 迁移阶段

### Phase 0: 脚手架 ✅ (已完成)
- 创建 `server/` 目录结构, `pyproject.toml`
- FastAPI app 启动, SQLite schema 建表 (conversations, messages, knowledge_documents, knowledge_chunks)
- `GET /api/health` 通过, Vite proxy 验证 OK

### Phase 1: 聊天代理 ✅ (已完成)
- 实现 `POST /api/chat` — httpx 调用 DeepSeek 流式 API, 转发 SSE delta
- 实现 Conversation CRUD (SQLite 持久化, 含 messages)
- 后端 mock 模式 (`llm_service.mock_chat_stream()`)
- 前端 `src/api/llm.ts` 改为调 `/api/chat`, SSE 读取逻辑不变
- 前端 `src/pages/chat.vue` 去掉 `simulateMockResponse`, `buildContext` 调用
- 新增 `src/api/conversation.ts`, `Citation` 类型, `AssistantMsg` 引用展示
- **验证通过**: ✅ mock 模式 SSE ✅ DeepSeek 流式代理 ✅ 消息持久化 ✅ TypeScript 零错误

### Phase 2: Agent 基础设施 + 上下文压缩

> **目标**: 为后续 ReAct Agent 打好地基，同时完成上下文压缩迁移。

#### Phase 2a: LLM Provider 抽象
- 新增 `server/app/services/llm_provider.py` — `LLMProvider` Protocol 接口
- 将 `llm_service.py` 中的 `deepseek_chat_stream` 重构为 `DeepSeekProvider`
- 实现 `MockProvider`，与 `DeepSeekProvider` 共用接口
- `chat.py` 通过依赖注入获取 provider，不再硬编码

#### Phase 2b: Tool 接口定义
- 新增 `server/app/tools/` 目录，定义 `BaseTool` 基类：
  - `name`, `description`, `parameters` (JSON Schema)
  - `async execute(**kwargs) -> ToolResult`
- 将 RAG 检索包装为 `SearchKnowledgeTool`
- 新增 `services/tool_registry.py` — Tool 注册/查询

#### Phase 2c: SSE 事件类型化
- 后端 SSE 增加事件类型（`event: delta / tool_call / tool_result / done`）
- 新增 `services/agent_service.py` — Agent Loop 骨架（占位，Phase 3 实现 ReAct）
- 前端 `chat.vue` SSE 循环适配多事件类型
- 前端新增 `ToolCallBanner.vue` — 展示 Tool 调用中间步骤

#### Phase 2d: 上下文压缩迁移
- 将 `src/utils/context/context.ts` 移植到 `context_service.py`
- 使用 `tiktoken` 精准计数（替代 `Math.ceil(len/2.5)`）
- 摘要状态存 SQLite (`summary_text`, `summarized_count`)
- 前端删除 `src/utils/context/`
- **验证**: 超长对话不超 token, 摘要正确合并

### Phase 2 验证清单
- ✅ LLM Provider 切换（Mock ↔ DeepSeek）通过同一接口
- ✅ Tool 注册和调用流程通路
- ✅ SSE 新事件类型前端正确解析
- ✅ 超长对话上下文压缩正常工作
- ✅ 前端展示 Tool 调用中间步骤

### Phase 3: RAG 管道 (~3天)
- 实现文档加载/分块/嵌入/ChromaDB 存储
- 实现 `retrieve_and_augment()` → 增强 Prompt
- 知识库 CRUD API
- 前端: `KnowledgePanel.vue`, RAG toggle, `CitationBanner.vue`
- **验证**: 上传文档 → 问相关问题 → 回答引用文档内容 + 显示来源

### Phase 4: 文件上传迁移 (~1天)
- 聊天中的文件附件改为先 POST 上传, 拿到 document ID 后在 chat 请求中引用
- 前端 `FileUpload.vue` 改为调后端上传而非 `FileReader`
- **验证**: 对话中传文件 → AI 基于文件内容回答

### Phase 5: 收尾 (~1天)
- 全局错误处理, 日志, SQLite 索引优化
- 更新 CLAUDE.md 文档
- 清理死代码, 删除 `.env` 中的前端 key, 提供 `server/.env.example`
- **端到端验证**: 新建会话 → 上传知识库 → RAG 对话 → 引用展示 → 会话持久化

---

## 关键决策记录

1. **SSE 格式**: 后端转发 DeepSeek 原始 `{choices: [{delta: {content, reasoning_content}}]}` 格式，前端 [chat.vue:243-276](src/pages/chat.vue#L243-L276) 零改动
2. **LLM 调用**: 使用 `httpx` 直调 DeepSeek API，不用 LangChain 的 ChatOpenAI 包装——流式控制更精确
3. **Vector Store**: ChromaDB 本地模式，零外部依赖，PersistentClient 持久化
4. **嵌入模型**: OpenAI text-embedding-3-small 为首选，抽象接口支持后续替换本地模型
5. **Mock 模式**: 移至后端实现，统一 SSE 代码路径
6. **会话持久化**: 后端 SQLite 为 source of truth，前端 Pinia 为工作缓存 + localStorage 离线兜底
7. **代码清洁**: 功能从前端迁移至后端后，**必须同步删除**前端不再使用的相关代码（模块、工具函数、mock 数据等），保持代码库无冗余。已完成清理：`src/utils/context/`、`src/mock/`

---

## 验证方法

每个 Phase 结束后：
1. `pnpm dev` 启动前端 (port 3000)
2. `uvicorn app.main:app --port 3001` 启动后端
3. 浏览器打开 `localhost:3000`，完成以下流程：
   - 创建新会话 → 发送消息 → 观察流式输出 → 停止生成
   - 刷新页面 → 会话和消息保持
   - 上传 2-3 个文档 → 开启 RAG → 提问 → 回答引用来源
   - 超长对话 (30+ 轮) → 确认上下文压缩正常工作
   - 切换模型 (mock/deepseek/deepseek-think) → 确认各模式正常

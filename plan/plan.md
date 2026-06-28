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
  ├── 保留: UI 组件、Markdown 渲染、Pinia Store (内存缓存)
  ├── 改动: src/api/llm.ts → 调 /api/chat (不再直连 DeepSeek)
  └── 新增: 知识库管理面板、RAG 开关、引用展示
        │ SSE (TransformStream，支持 typed events)
FastAPI (Python, port 3001)
  ├── POST /api/chat          → httpx 代理 DeepSeek (流式 SSE)
  ├── /api/conversations/*     → CRUD (SQLite 持久化)
  ├── /api/knowledge/documents → 知识库文档管理
  └── RAG Pipeline:
      文档加载 → 中文友好分块 → ZhipuAI embedding-2 向量化
      → ChromaDB 存储 → 相似度检索 → 增强 Prompt → LLM 回答
```

---

## 后端项目结构

```
server/
  pyproject.toml                ✅
  .env                          ✅ DEEPSEEK_API_KEY, ZHIPUAI_API_KEY
  .env.example                  ✅ 配置模板
  app/
    main.py                     ✅ FastAPI app, CORS, lifespan (ChromaDB init)
    config.py                   ✅ pydantic-settings (DeepSeek + ZhipuAI + OpenAI)
    api/
      __init__.py               ✅
      deps.py                   ✅ get_db 依赖注入
      chat.py                   ✅ POST /api/chat (SSE, context + RAG + Agent)
      conversations.py          ✅ CRUD /api/conversations + messages
      knowledge.py              ✅ CRUD /api/knowledge/documents
    core/
      __init__.py               ✅
      database.py               ✅ SQLAlchemy async engine + aiOSQLite
      sse.py                    ✅ SSE 类型化事件 (delta/tool_call/tool_result/done/error)
    models/
      __init__.py               ✅
      conversation.py           ✅ Conversation, Message ORM
      knowledge.py              ✅ KnowledgeDocument, KnowledgeChunk ORM
    schemas/
      __init__.py               ✅
      chat.py                   ✅ ChatRequest, ConversationCreate/Out, MessageOut, DocumentOut
    services/
      __init__.py               ✅
      llm_provider.py           ✅ LLM Provider 抽象 (DeepSeekProvider / MockProvider)
      llm_service.py            ✅ 持久化辅助函数 (persist_user/assistant_message)
      context_service.py        ✅ 上下文压缩 (tiktoken 精准计数, 80K 阈值, 20 窗口)
      rag_service.py            ✅ RAG 编排 (ingest + augment_chat + delete)
      agent_service.py          ✅ AgentService (无 Tool 时直通 LLM, Phase 5 实现 ReAct)
      tool_registry.py          ✅ Tool 注册/查询 (Phase 5 ReAct 使用)
    tools/
      __init__.py               ✅
      base.py                   ✅ BaseTool 基类 (name, description, parameters, execute)
      search_knowledge.py       🔜 SearchKnowledgeTool (Phase 5: RAG 检索包装为 Tool)
    rag/
      __init__.py               ✅
      loader.py                 ✅ 文档加载 (txt/md/pdf/csv/json 等)
      splitter.py               ✅ 中文优化分块 (500 字符, 10% 重叠)
      embedder.py               ✅ ZhipuAI > OpenAI > ONNX 三级 fallback
      retriever.py              ✅ ChromaDB 检索 (阈值 1.5, top-k=5)
      prompt.py                 ✅ RAG prompt 模板 + citations 构建
  data/                         ✅ gitignored
    chat.db                     ✅ SQLite
    chroma/                     ✅ ChromaDB 持久化
    uploads/                    ✅ 上传文档存储
```

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

**响应**: SSE typed events (`event: delta / citations / done`):

```
event: delta
data: {"choices":[{"delta":{"content":"RAG stands for"}}]}

event: delta
data: {"choices":[{"delta":{"content":" Retrieval-Augmented Generation."}}]}

event: citations
data: {"citations":[{"document":"notes.txt","snippet":"RAG is a...","score":0.62}]}

event: done
data: [DONE]
```

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
| POST | `/api/knowledge/documents` | multipart 上传 (支持多文件, txt/md/pdf/csv/json/log/xml/yml/ini/conf) |
| GET | `/api/knowledge/documents` | 文档列表 |
| DELETE | `/api/knowledge/documents/:id` | 删除 (级联删 chunks + 向量 + 源文件) |

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

> 向量数据仅存 ChromaDB (`data/chroma/`)，`knowledge_chunks` 是关系索引。源文件存 `data/uploads/`。

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
**默认**: ZhipuAI `embedding-2` (1024 维)，中文效果好，国内访问快。

**Fallback 链**: ZhipuAI → OpenAI → ONNX (本地)

### 检索逻辑
```
query → embed_query → ChromaDB query(embeddings=[...], k=5)
  → 余弦距离过滤 (distance < 1.5)
  → 归一化相似度: 1.0 - distance/2.0
  → 格式化注入 system prompt
```

### 存储流程
```
上传文件 → data/uploads/{uuid}.ext (落盘)
  → load (LangChain)
  → split (500 字符/块)
  → embed (ZhipuAI, 预计算向量, 绕过 ChromaDB 超时)
  → ChromaDB add (ids + documents + embeddings + metadatas)
  → SQLite 写入 knowledge_chunks (chroma_id 映射)
```

---

## 前端改动清单

> ✅ = 已完成 &nbsp; 🔜 = 待实现

| 文件 | 状态 | 说明 |
|------|------|------|
| `src/api/llm.ts` | ✅ | 调 `/api/chat`，SSE typed events 兼容 |
| `src/pages/chat.vue` | ✅ | buildLLMMessages 支持聊天附件; SSE 处理 delta/tool_call/citations/done; mock 由后端接管 |
| `src/components/chat/types.ts` | ✅ | 新增 `Citation` 接口 |
| `src/components/chat/AssistantMsg.vue` | ✅ | 引用来源展示 + ToolCallBanner 集成 |
| `src/components/chat/ChatInput.vue` | ✅ | RAG toggle 按钮 |
| `src/components/chat/ToolCallBanner.vue` | ✅ | Tool 调用中间步骤展示 |
| `src/components/knowledge/KnowledgePanel.vue` | ✅ | 知识库管理面板 |
| `src/api/conversation.ts` | ✅ | 会话后端 CRUD 客户端 |
| `src/api/knowledge.ts` | ✅ | 知识库文档 CRUD 客户端 |
| `src/stores/conversation.ts` | ✅ | 移除 localStorage persist; 改为后端加载 |
| `src/utils/transform.ts` | ✅ | SSE 解析支持 typed events (event: + data:) |
| `src/main.ts` | ✅ | 移除 pinia-plugin-persistedstate |
| `src/mock/` | ✅ 已删除 | mock 移至后端 |
| `src/utils/context/` | ✅ 已删除 | 上下文压缩移至后端 |
| `.env` (VITE_DEEPSEEK_API_KEY) | ✅ | 密钥移至 `server/.env` |

---

## 迁移阶段

### Phase 0: 脚手架 ✅
- `server/` 目录, `pyproject.toml`, FastAPI, SQLite, health check

### Phase 1: 聊天代理 ✅
- `POST /api/chat` SSE 代理, Conversation CRUD, 后端 mock
- 前端 `llm.ts` + `chat.vue` + `types.ts` 改写

### Phase 2: Agent 基础设施 ✅
- LLM Provider 抽象 (`DeepSeekProvider / MockProvider`)
- Tool 接口 (`BaseTool` + `ToolRegistry`)
- SSE 事件类型化 (`delta / tool_call / tool_result / done / error`)
- `AgentService` 骨架
- 上下文压缩移植 (`context_service.py`, tiktoken 精准计数)

### Phase 3: RAG 管道 ✅
- 文档加载/分块/ZhipuAI 嵌入/ChromaDB 存储
- RAG 集成到 chat 流程 (`augment_chat`)
- 知识库 CRUD API
- 前端 KnowledgePanel + RAG toggle + 引用展示
- localStorage 移除, 改为后端 SQLite 加载

### Phase 4: 收尾 (当前)
- 更新 plan.md 状态标记
- 全局错误处理 (后端异常中间件 + 前端 toast)
- SQLite 索引优化
- CLAUDE.md 同步更新
- 端到端验证

### Phase 5: Agent (后续)
- ReAct Agent Loop (`agent_service._agent_loop`)
- `SearchKnowledgeTool` — RAG 检索注册为 Tool
- Tool 调用在 SSE 流中透传 → 前端 `ToolCallBanner` 渲染

---

## 关键决策记录

1. **SSE 格式**: 后端转发 DeepSeek 兼容 delta 格式 + typed events (`event: delta/citations/done`)，前端零改动兼容
2. **LLM 调用**: `httpx` 直调 DeepSeek API，不用 LangChain ChatOpenAI——流式控制更精确
3. **Vector Store**: ChromaDB PersistentClient，手动预计算 embedding 避免内部超时
4. **嵌入模型**: ZhipuAI `embedding-2` 为首选 (国内快)，OpenAI → ONNX 三级 fallback
5. **Mock 模式**: 移至后端 `MockProvider`，统一 SSE 代码路径
6. **会话持久化**: 后端 SQLite 为 source of truth，前端 Pinia 为内存缓存
7. **代码清洁**: 功能迁移至后端时，同步删除前端冗余代码 (已完成: `mock/`, `context/`, `pinia-plugin-persistedstate`)
8. **上下文压缩**: 在 RAG 检索**之前**执行 → 先压缩释放 token 空间 → 再注入 RAG 上下文 → 最后发给 LLM
9. **RAG 静默降级**: embedding 失败/知识库空/无匹配 → 照常对话

---

## 验证方法

1. `pnpm dev` 启动前端 (port 3000)
2. `cd server && uvicorn app.main:app --port 3001` 启动后端
3. 浏览器打开 `localhost:3000`:
   - 创建新会话 → 发送消息 → 流式输出 → 停止生成
   - 刷新页面 → 会话和消息从后端加载
   - 上传 2-3 个文档 → 开启 RAG → 提问 → 回答引用来源
   - 超长对话 (30+ 轮) → 上下文压缩正常工作
   - 切换模型 (mock/deepseek/deepseek-think) → 各模式正常

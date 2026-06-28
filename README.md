# ChatAI — RAG知识库对话平台

基于 **Vue 3 + FastAPI + LangChain + ChromaDB** 构建的 AI 知识库对话平台。支持 DeepSeek 模型流式对话、会话管理、文档上传、Markdown 渲染和 RAG（检索增强生成）。

## 特性

- **流式对话**: SSE 实时流式输出，支持推理过程展示 (`<think>` 标签)
- **知识库 RAG**: 上传文档 → 自动分块向量化 → 对话中检索增强回答 → 引用来源
- **会话管理**: SQLite 持久化，支持多会话切换、上下文自动压缩
- **Markdown 渲染**: 代码高亮、LaTeX 数学公式、Mermaid 图表
- **多模型**: DeepSeek / DeepSeek-Think / Mock 模式
- **Agent 基础设施**: LLM Provider 抽象、Tool 注册、SSE 类型化事件（为 ReAct Agent 预留）

## 项目结构

```
chatAI/
├── frontend/                   # Vue 3 前端
│   ├── src/
│   │   ├── api/                # 后端 API 客户端 (chat, conversations, knowledge)
│   │   ├── components/
│   │   │   ├── chat/           # 聊天组件 (消息、输入框、文件上传、引用展示)
│   │   │   ├── knowledge/      # 知识库管理面板
│   │   │   └── layout/         # 侧边栏、会话列表
│   │   ├── pages/              # 聊天主页面
│   │   ├── stores/             # Pinia 状态管理
│   │   ├── utils/              # Markdown 渲染、SSE 解析、代码复制
│   │   └── styles/             # SCSS 变量、Markdown 样式
│   ├── vite.config.ts
│   └── package.json
├── server/                     # Python FastAPI 后端
│   ├── app/
│   │   ├── api/                # chat, conversations, knowledge 端点
│   │   ├── core/               # database, SSE 事件
│   │   ├── models/             # SQLAlchemy ORM
│   │   ├── schemas/            # Pydantic 模型
│   │   ├── services/           # llm_provider, context, rag, agent, tool_registry
│   │   ├── tools/              # BaseTool 接口
│   │   └── rag/                # loader, splitter, embedder, retriever, prompt
│   ├── data/                   # SQLite + ChromaDB + uploads (gitignored)
│   ├── .env.example
│   └── pyproject.toml
├── plan/                       # 项目规划文档
├── CLAUDE.md                   # Claude Code 开发指南
└── README.md
```

## 快速开始

### 环境要求

- **Node**: `^20.19.0 || >=22.12.0`
- **Python**: `>=3.11`
- **pnpm**: 前端包管理

### 1. 配置后端

```bash
cd server
cp .env.example .env
```

编辑 `server/.env`，填入 API Key：

```env
# LLM (必填)
DEEPSEEK_API_KEY=sk-your-deepseek-key

# Embedding (必填，用于知识库 RAG)
ZHIPUAI_API_KEY=your-zhipu-api-key
```

> 嵌入模型优先级: ZhipuAI `embedding-2` → OpenAI `text-embedding-3-small` → ONNX 本地

### 2. 安装依赖

```bash
# 前端
cd frontend
pnpm install

# 后端
cd ../server
pip install -r requirements.txt
```

### 3. 启动

```bash
# 终端 1: 启动后端 (port 3001)
cd server
uvicorn app.main:app --port 3001 --reload

# 终端 2: 启动前端 (port 3000)
cd frontend
pnpm dev
```

浏览器打开 `http://localhost:3000`。

## 使用指南

### 基本对话

1. 点击左侧「新建对话」
2. 选择模型（DeepSeek / DeepSeek-Think / Mock）
3. 输入问题，回车发送
4. 流式输出实时展示，支持 Markdown 渲染

### 知识库 RAG

1. 点击右下角 📚 按钮打开知识库面板
2. 上传文档（支持 txt, md, pdf, csv, json, log, xml, yml, ini, conf）
3. 文档自动分块 → 向量化 → 存入 ChromaDB
4. 在输入框中开启 📚 RAG 按钮
5. 提问时自动检索相关文档片段，回答附带引用来源

### 聊天附件

- 发送消息时可拖入文本文件作为附件
- 附件内容自动拼接到消息中发给 LLM
- 支持 txt, md, json, csv, xml, yml, log 等格式

## API 文档

### POST /api/chat (SSE 流式)

```json
// 请求
{
  "conversation_id": "uuid-or-null",
  "model": "deepseek",
  "messages": [{"role": "user", "content": "什么是 RAG?"}],
  "use_rag": true
}

// 响应 (SSE typed events)
event: delta     → {"choices":[{"delta":{"content":"RAG 是..."}}]}
event: citations → {"citations":[{"document":"notes.txt","snippet":"...","score":0.62}]}
event: done      → [DONE]
```

### 其他端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/conversations` | 会话列表 |
| POST | `/api/conversations` | 创建会话 |
| DELETE | `/api/conversations/:id` | 删除会话 |
| GET | `/api/conversations/:id/messages` | 获取消息 |
| POST | `/api/knowledge/documents` | 上传知识库文档 |
| GET | `/api/knowledge/documents` | 文档列表 |
| DELETE | `/api/knowledge/documents/:id` | 删除文档 |
| GET | `/api/health` | 健康检查 |

## 技术栈

### 前端
- Vue 3 + TypeScript + Vite
- Naive UI + Tailwind CSS 4 + SCSS
- Pinia 状态管理
- markdown-it + highlight.js + KaTeX

### 后端
- FastAPI + uvicorn
- SQLAlchemy async + aiOSQLite
- httpx (DeepSeek API 代理)
- sse-starlette (SSE 流式)
- LangChain + ChromaDB (RAG)
- ZhipuAI embedding-2 (向量化)
- tiktoken (Token 计数)

## 架构

详细架构说明见 [CLAUDE.md](CLAUDE.md)，迁移计划见 [plan/plan.md](plan/plan.md)。

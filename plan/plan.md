# Plan: AI 知识库对话平台 — 企业级改进计划

---

## 对比分析: EchoMind vs chatAI

通过深度对比 EchoMind（智能客服 AI 后端）和 chatAI（AI 知识库对话平台），以下从多个维度分析 chatAI 可做的企业级改进。

### 两项目定位差异

| 维度 | EchoMind v2.0 | chatAI |
|------|--------------|--------|
| **类型** | 纯后端 API（无前端） | 全栈（Vue 3 + FastAPI） |
| **场景** | 智能客服（多 Agent 路由） | 通用知识库对话 |
| **用户** | 多用户（user_id 参数） | 单用户本地工具 |
| **Agent** | 多 Agent 编排 + 性能路由 | 单 Agent（LangGraph） |
| **部署** | Docker + Nginx + docker-compose | 手动 pnpm dev + uvicorn |
| **存储** | Redis + ChromaDB | SQLite + ChromaDB |
| **监控** | Prometheus + 异常检测 + 告警 | 请求日志中间件 |

---

## chatAI 企业级改进清单

> 优先级: 🔴 P0 必须 | 🟠 P1 重要 | 🟡 P2 值得做 | 🟢 P3 锦上添花

---

## 一、容器化与部署 (P0) 🔴

### 1.1 现状
- 前端: 手动 `pnpm dev`
- 后端: 手动 `uvicorn app.main:app --port 3001`
- 无容器化，无编排，无法在生产环境部署

### 1.2 EchoMind 参照
- 多阶段 Dockerfile（base → deps → prod/dev）
- docker-compose.yml 编排 5 个服务（app, redis, chromadb, prometheus, nginx）
- 部署脚本（build-image.sh, run-image.sh, docker-deploy.sh）
- ONNX 模型预下载避免运行时超时

### 1.3 改进方案

**后端 Dockerfile**（多阶段构建）:
```dockerfile
# Stage 1: base — Python 3.12
# Stage 2: deps — pip install requirements.txt
# Stage 3: prod — 复制源码，预下载 ChromaDB ONNX 模型
# Stage 4: dev — 热重载开发模式
```

**前端 Dockerfile**（多阶段构建）:
```dockerfile
# Stage 1: build — pnpm build
# Stage 2: serve — Nginx 静态文件服务 + /api 反向代理
```

**docker-compose.yml**:
```yaml
services:
  frontend:    # Nginx 静态服务 (:80)
  backend:     # FastAPI (:3001)
  chromadb:    # ChromaDB 独立服务（可选，当前 PersistentClient 也够用）
```

**收益**: 一键启动 `docker compose up`，生产就绪，环境一致性

---

## 二、测试体系 (P0) 🔴

### 2.1 现状
- vitest + @vue/test-utils + jsdom 已安装
- **零测试文件** — 没有任何 .test.ts / .spec.ts
- 后端无任何测试框架
- tsconfig.json 显式排除了 `__tests__/`

### 2.2 EchoMind 参照
- 无单元测试，但有 LLM-as-Judge 评估框架
- 内置测试用例（意图识别 + 对话质量）
- 回归检测（对比 baseline）

### 2.3 改进方案

**前端**（vitest 已就绪，补齐测试文件）:
```
frontend/src/__tests__/
  components/
    ChatInput.test.ts          # 输入框行为、文件上传、RAG 开关
    AssistantMsg.test.ts       # Markdown 渲染、引用展示、代码复制
    UserMsg.test.ts            # 用户消息展示、文件附件展示
    KnowledgePanel.test.ts     # 文档上传/删除、状态展示
  stores/
    conversation.test.ts       # Pinia store: 会话 CRUD、消息管理
  api/
    llm.test.ts                # SSE 解析、错误处理、abort
  utils/
    transform.test.ts          # SSE stream 解析
    markdown.test.ts           # Markdown 渲染管道
```

**后端** (pytest + httpx AsyncClient):
```
server/tests/
  api/
    test_chat.py               # SSE 流式、消息持久化、错误处理
    test_conversations.py      # CRUD 端点
    test_knowledge.py          # 文档上传/删除
  services/
    test_rag_service.py        # RAG 管道: ingest + augment + delete
    test_agent_service.py      # Agent 工具调用
  rag/
    test_splitter.py           # 中文分块正确性
    test_embedder.py           # Fallback 链
    test_retriever.py          # 检索阈值、top-k
```

**目标覆盖率**: 核心路径 80%+

---

## 三、可观测性 (P1) 🟠

### 3.1 现状
- 后端: 仅一个 `log_requests` 中间件（print 方式记录 method/path/status/duration）
- 前端: 无任何监控
- 无结构化日志、无指标、无告警

### 3.2 EchoMind 参照
- Prometheus 指标（`prometheus_client`）
- `PerformanceMonitor` 在线监控 + Z-score 异常检测
- Webhook 告警（fire-and-forget 异步发送）
- 监控→编排器反馈闭环（影响 Agent 路由评分）
- 可配置的监控间隔和异常检测阈值

### 3.3 改进方案

**结构化日志** (Python `logging` 替代 `print`):
```python
# server/app/core/logging.py
import logging
import json
import time

def setup_logging(level: str = "INFO"):
    """配置结构化 JSON 日志"""
    ...

class JsonFormatter(logging.Formatter):
    """输出 {"timestamp":..., "level":..., "message":..., "path":..., "duration_ms":...}"""
    ...
```

**Prometheus 指标** (新增依赖 `prometheus-client`):
```python
# server/app/monitor/metrics.py
from prometheus_client import Counter, Histogram, Gauge

chat_requests_total = Counter('chat_requests_total', 'Total chat requests', ['model'])
chat_request_duration = Histogram('chat_request_duration_seconds', 'Chat request duration')
rag_query_duration = Histogram('rag_query_duration_seconds', 'RAG query duration')
active_streams = Gauge('active_sse_streams', 'Active SSE connections')
embedding_failover_total = Counter('embedding_failover_total', 'Embedding fallback count', ['from', 'to'])
db_connections = Gauge('db_connections', 'Active DB connections')
```

**健康检查增强**:
```python
# GET /api/health 增强返回
{
  "status": "healthy",
  "checks": {
    "database": {"status": "ok", "latency_ms": 2.3},
    "chromadb": {"status": "ok", "collection_count": 5},
    "zhipuai": {"status": "ok", "latency_ms": 120},
    "deepseek": {"status": "ok", "latency_ms": 200}
  },
  "uptime_seconds": 86400,
  "version": "2.0.0"
}
```

---

## 四、韧性模式 (P1) 🟠

### 4.1 现状
- embedding 有三级 fallback（ZhipuAI → OpenAI → ONNX），✅ 已做好
- RAG 静默降级（失败照常对话），✅ 已做好
- 无断路器、无超时控制、无重试策略

### 4.2 EchoMind 参照
- **Circuit Breaker**: 三态（CLOSED → OPEN → HALF_OPEN），5 次连续失败 → 断路 60s → 半开探测
- **Timeout**: `asyncio.wait_for(handler, timeout=30s)` 包裹所有工具调用
- **Fallback 链**: ChromaDB Server → PersistentClient; 远程 embedding → 本地 n-gram
- **Unicode 清理**: 所有 LLM 调用前 `encode("utf-8", errors="ignore").decode("utf-8")`

### 4.3 改进方案

**断路器** (新增 `server/app/core/circuit_breaker.py`):
```python
from enum import Enum
import time
import asyncio

class CircuitState(Enum):
    CLOSED = "closed"         # 正常
    OPEN = "open"             # 断路
    HALF_OPEN = "half_open"   # 探测恢复

class CircuitBreaker:
    """保护外部 API 调用（DeepSeek, ZhipuAI, ChromaDB）"""
    def __init__(self, failure_threshold=5, recovery_timeout=60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = CircuitState.CLOSED
        self.last_failure_time = None

    async def call(self, coro, fallback=None):
        """执行受保护的调用，断路时走 fallback"""
        ...
```

**应用位置**:
- DeepSeek Chat API（LLM 调用）
- ZhipuAI Embedding API（向量化）
- ChromaDB 操作（检索）

**LLM 重试策略**:
```python
# server/app/core/retry.py
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
async def call_llm_with_retry(...):
    ...
```

---

## 五、API 文档与规范 (P1) 🟠

### 5.1 现状
- FastAPI 自动生成 `/docs` (Swagger) 和 `/redoc`
- 但未配置 title/description/version
- 请求/响应 Schema 未充分利用 Pydantic Field 描述
- 无 OpenAPI tags 分类

### 5.2 EchoMind 参照
- 完整的 Swagger UI（`/docs`）
- 可通过 `ENABLE_SWAGGER_UI` 功能开关控制

### 5.3 改进方案

```python
# server/app/main.py
app = FastAPI(
    title="chatAI API",
    description="AI 知识库对话平台 — RAG 增强的智能对话系统",
    version="2.1.0",
    docs_url="/docs" if settings.ENABLE_SWAGGER_UI else None,
    redoc_url="/redoc" if settings.ENABLE_SWAGGER_UI else None,
    openapi_tags=[
        {"name": "chat", "description": "对话与 SSE 流式"},
        {"name": "conversations", "description": "会话管理"},
        {"name": "knowledge", "description": "知识库文档"},
        {"name": "health", "description": "健康检查"},
    ],
)
```

**Pydantic Schema 增强**:
```python
class ChatRequest(BaseModel):
    conversation_id: str | None = Field(None, description="会话 ID，为空则创建新会话")
    model: str = Field("deepseek-v4-flash", description="模型标识: deepseek-v4-flash / deepseek-reasoner")
    messages: list[Message] = Field(..., description="对话消息列表")
    files: list[FileRef] | None = Field(None, description="聊天附件引用")
```

---

## 六、安全加固 (P1) 🟠

### 6.1 现状
- CORS 限定 `localhost:3000`（开发环境合理）
- 无认证机制
- 无速率限制
- 文件上传仅有扩展名检查，无内容校验
- API Key 在 `.env` 中（未加密）

### 6.2 EchoMind 参照
- Nginx 层速率限制（`limit_req_zone`, 10 req/s, burst 20）
- 安全响应头（X-Frame-Options, X-Content-Type-Options, X-XSS-Protection, Referrer-Policy）
- `SECRET_KEY` / `JWT_SECRET_KEY` 已定义但未使用（预留扩展点）

### 6.3 改进方案

**速率限制** (新增依赖 `slowapi`):
```python
# server/app/core/rate_limit.py
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

# 在 main.py 中
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@router.post("/chat")
@limiter.limit("30/minute")  # 对话端点: 30次/分钟
async def chat(...): ...

@router.post("/knowledge/documents")
@limiter.limit("10/minute")  # 上传端点: 10次/分钟
async def upload_documents(...): ...
```

**文件上传安全增强**:
```python
# server/app/core/security.py
import magic  # python-magic 做 MIME 类型检测

def validate_file(file: UploadFile) -> None:
    """不仅检查扩展名，还检查 MIME 类型和文件头魔数"""
    # 1. 扩展名白名单
    # 2. MIME 类型检测
    # 3. 文件大小限制（MAX_UPLOAD_SIZE_MB）
    # 4. 文件名安全化（防路径穿越）
    ...
```

**安全响应头中间件**:
```python
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response
```

---

## 七、缓存层 (P2) 🟡

### 7.1 现状
- 无任何缓存机制
- 每次请求都完整走 Chat + RAG 流程
- embedding 结果未缓存（相同文本重复向量化）

### 7.2 EchoMind 参照
- LFU/LRU 缓存（LRU dict，max 1000 entires，满时淘汰最早 500）
- Tool 结果 TTL 缓存（默认 300s）
- 意图识别结果缓存

### 7.3 改进方案

**Embedding 缓存** (高收益):
```python
# server/app/core/cache.py
import hashlib
import time
from collections import OrderedDict

class LRUCache:
    """简单的 LRU 缓存，用于 embedding 结果"""
    def __init__(self, max_size=1000):
        self.cache = OrderedDict()
        self.max_size = max_size

    def get(self, key): ...
    def set(self, key, value): ...

# 使用: 对文档内容 MD5 → 缓存 embedding 向量
# 避免相同文档重复调用 ZhipuAI API
```

**RAG 查询缓存**:
```python
# 对相同 query 在 TTL 内返回缓存的检索结果
# 避免短时间重复查询重复检索 + 重复 embedding
```

---

## 八、评估框架 (P2) 🟡

### 8.1 现状
- 无任何质量评估机制
- 依赖人工验证 RAG 回答质量

### 8.2 EchoMind 参照
- LLM-as-Judge: 4 维度评分（相关性、准确性、完整性、帮助性）
- 通过阈值: 综合分 >= 0.75
- 意图识别准确率评估
- 回归检测: 对比历史 baseline，标记降级 > 5%

### 8.3 改进方案

```python
# server/evaluation/
#   __init__.py
#   evaluator.py      # RAG 回答质量评估 (LLM-as-Judge)
#   test_cases.py     # 内置测试用例

class RAGEvaluator:
    """RAG 回答质量评估"""
    DIMENSIONS = ["relevance", "accuracy", "completeness", "helpfulness"]

    async def evaluate(self, question: str, answer: str, citations: list) -> QualityScores:
        """用 LLM 对回答进行四维度打分"""
        ...

    async def run_suite(self) -> EvalReport:
        """运行全部测试用例，生成评估报告"""
        ...

# POST /eval/run — 手动触发评估
# GET /eval/report — 查看最新评估报告
```

**内置测试用例** (5-10 个):
- 事实性查询（"产品支持哪些文件格式？"）
- 综合性查询（"总结文档的主要内容"）
- 无匹配查询（"今天天气怎么样？"）— 验证不编造
- 跨文档查询（涉及 2+ 文档）

---

## 九、后端代码质量 (P2) 🟡

### 9.1 现状
- 前端: ESLint + Oxlint + EditorConfig ✅
- 后端: **无任何 lint/format 工具**

### 9.2 改进方案

```toml
# server/pyproject.toml 新增

[tool.ruff]
target-version = "py311"
line-length = 100
select = ["E", "F", "I", "N", "W", "UP"]

[tool.ruff.format]
quote-style = "double"

[tool.mypy]
python_version = "3.11"
strict = false
warn_return_any = true
warn_unused_ignores = true

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

**package.json 新增脚本**:
```json
{
  "lint:backend": "cd server && ruff check app/ && ruff format --check app/",
  "typecheck:backend": "cd server && mypy app/",
  "test": "vitest run",
  "test:backend": "cd server && pytest"
}
```

---

## 十、CI/CD 流水线 (P2) 🟡

### 10.1 现状
- `.github/workflows/` 目录存在但为空

### 10.2 改进方案

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
      - uses: actions/setup-node@v4
        with: { node-version: '22', cache: 'pnpm', cache-dependency-path: frontend/pnpm-lock.yaml }
      - run: cd frontend && pnpm install
      - run: cd frontend && pnpm lint
      - run: cd frontend && pnpm type-check
      - run: cd frontend && pnpm test
      - run: cd frontend && pnpm build

  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: cd server && pip install -r requirements.txt
      - run: cd server && ruff check app/
      - run: cd server && pytest
```

---

## 十一、功能开关 (P2) 🟡

### 11.1 现状
- 所有功能硬编码，无开关控制

### 11.2 EchoMind 参照
```
ENABLE_SWAGGER_UI=true
ENABLE_MONITORING=true
ENABLE_EVALUATION=true
```

### 11.3 改进方案

在 `server/app/config.py` 中新增:
```python
# 功能开关
ENABLE_SWAGGER_UI: bool = True
ENABLE_MONITORING: bool = True       # Prometheus 指标
ENABLE_EVALUATION: bool = True       # 评估 API
ENABLE_RATE_LIMIT: bool = True       # 速率限制

# 调试开关
DEV_MOCK_LLM: bool = False           # 开发时使用 Mock LLM
DEV_LOG_LLM_PROMPTS: bool = False    # 开发时打印完整 prompt
```

---

## 十二、错误处理体系化 (P2) 🟡

### 12.1 现状
- 后端: 全局 `ValueError` → 400, `Exception` → 500
- 前端: API 层 throw Error, 组件级 try/catch
- 无统一错误码、无用户友好消息

### 12.2 改进方案

**统一错误响应格式**:
```python
# server/app/core/exceptions.py
class AppError(Exception):
    """应用异常基类"""
    def __init__(self, code: str, message: str, status_code: int = 400, detail: dict = None):
        self.code = code          # "RAG_EMBED_FAILED"
        self.message = message    # "知识库向量化失败，请稍后重试"
        self.status_code = status_code
        self.detail = detail or {}

class ConversationNotFound(AppError): ...
class DocumentTooLarge(AppError): ...
class EmbeddingFailed(AppError): ...
```

**全局异常处理器改进**:
```python
@app.exception_handler(AppError)
async def app_error_handler(request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message, "detail": exc.detail}}
    )
```

**前端错误处理 Hook**:
```typescript
// frontend/src/hooks/useErrorHandler.ts
export function useErrorHandler() {
  function handleApiError(error: Error) {
    if (error instanceof AppError) {
      window.$message?.error(error.message)  // 用户友好消息
    } else {
      window.$message?.error("服务异常，请稍后重试")
      console.error("[Unhandled]", error)
    }
  }
  return { handleApiError }
}
```

---

## 十三、前端架构优化 (P3) 🟢

### 13.1 现状
- 无路由（单页 chat）
- 无懒加载
- 无 Suspense 边界
- 无请求去重/取消（除 AbortController）
- 无虚拟滚动（长消息列表）

### 13.2 改进方案

| 优化 | 说明 | 收益 |
|------|------|------|
| **请求去重** | 相同 query 并发时合并请求 | 减少重复 LLM 调用 |
| **虚拟滚动** | 大量消息时只渲染可见区域 | 长对话性能 |
| **组件懒加载** | `defineAsyncComponent` + `Suspense` | 首屏加载速度 |
| **图片/文件预览** | 上传文件前本地预览 | 用户体验 |
| **错误边界** | `onErrorCaptured` 包裹关键区域 | 局部错误不影响全局 |

---

## 十四、国际化 (P3) 🟢

### 14.1 现状
- 所有 UI 文本硬编码中文
- 时间格式硬编码 `zh-CN`

### 14.2 改进方案

引入 `vue-i18n`:
```
frontend/src/locales/
  zh-CN.json    # 简体中文（默认）
  en-US.json    # 英文

// 使用
{{ $t('chat.input.placeholder') }}
{{ $t('knowledge.upload.success') }}
```

> 注: 当前阶段用户为中文用户，P3 优先级。架构上预留 i18n 接口即可。

---

## 实施优先级路线图

```
Phase 5: 企业基础 (当前建议)
  ├── 5.1 容器化 (Docker + docker-compose)              🔴 P0
  ├── 5.2 测试体系 (前端 vitest + 后端 pytest)           🔴 P0
  └── 5.3 API 文档完善 (Swagger + Schema 描述)           🟠 P1

Phase 6: 生产韧性
  ├── 6.1 结构化日志 + 健康检查增强                       🟠 P1
  ├── 6.2 断路器 + 重试 + Unicode 清理                    🟠 P1
  ├── 6.3 速率限制 + 安全响应头 + 文件上传安全             🟠 P1
  └── 6.4 错误处理体系化 (AppError + 统一响应格式)        🟡 P2

Phase 7: 质量基础设施
  ├── 7.1 后端 lint/format (ruff + mypy)                 🟡 P2
  ├── 7.2 CI/CD (GitHub Actions)                          🟡 P2
  ├── 7.3 功能开关 (config.py)                            🟡 P2
  └── 7.4 缓存层 (Embedding 缓存 + RAG 查询缓存)          🟡 P2

Phase 8: 评估与监控
  ├── 8.1 Prometheus 指标 + 性能监控                      🟠 P1
  ├── 8.2 RAG 评估框架 (LLM-as-Judge)                    🟡 P2
  └── 8.3 前端架构优化 (虚拟滚动 / 懒加载 / 错误边界)     🟢 P3

Phase 9: 锦上添花
  ├── 9.1 国际化 (vue-i18n)                                🟢 P3
  └── 9.2 多 Agent 协作 (适用场景评估后决定)               🟢 P3
```

---

## 关键决策记录

1. **容器化优先**: Docker 确保开发/生产环境一致性，是 CI/CD 的前提
2. **测试先行**: vitest 已安装但零测试是最大负债；先补齐核心流程测试
3. **不引入 Redis**: 单用户场景 SQLite + ChromaDB 够用；Redis 增加运维复杂度而收益有限
4. **不引入 Nginx**: 前端 Vite 开发服务器 + 后端 Uvicorn 在开发阶段足够；生产环境通过 Docker Nginx 处理
5. **断路器选轻量自研**: 依赖 `tenacity` 做重试，自定义 `CircuitBreaker` 做断路，避免引入重量级框架
6. **i18n 延后**: 当前用户群体为中文，架构预留接口，不急于实现多语言
7. **多 Agent 评估后再决定**: EchoMind 的多 Agent 路由是为客服场景设计（账单/技术/通用）；chatAI 的通用对话场景单 Agent + 工具调用已够用

---

## 对比总结

| 维度 | EchoMind | chatAI 当前 | chatAI 目标 |
|------|----------|------------|------------|
| **容器化** | ✅ Docker + compose | ❌ | ✅ |
| **测试** | ⚠️ 仅评估，无单测 | ❌ | ✅ 单测 + 评估 |
| **监控** | ✅ Prometheus + 异常检测 | ❌ | ✅ Prometheus |
| **断路器** | ✅ 三态 | ❌ | ✅ |
| **速率限制** | ✅ Nginx | ❌ | ✅ slowapi |
| **API 文档** | ✅ Swagger | ⚠️ 默认 | ✅ 完善 |
| **缓存** | ✅ LRU + TTL | ❌ | ✅ Embedding 缓存 |
| **安全头** | ✅ Nginx | ❌ | ✅ 中间件 |
| **CI/CD** | ⚠️ Shell 脚本 | ❌ | ✅ GitHub Actions |
| **代码质量(后端)** | ❌ | ❌ | ✅ ruff + mypy |
| **日志** | ⚠️ 基础 | ⚠️ print | ✅ 结构化 JSON |
| **错误体系** | ⚠️ 基础 | ⚠️ 基础 | ✅ AppError 体系 |
| **i18n** | ❌ | ❌ | 🟢 架构预留 |
| **多 Agent** | ✅ | ❌ | 🟢 评估后定 |

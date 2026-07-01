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

## 八、RAGAS 评估体系 (P0) 🔴

> RAGAS (Retrieval Augmented Generation Assessment) 是专为 RAG 系统设计的开源评估框架。
> 区别于简单 LLM-as-Judge，RAGAS 提供组件级评估（检索 + 生成分别打分），
> 且支持自动化测试数据集生成，适合持续集成。

### 8.1 RAGAS 核心指标

RAGAS 将 RAG 管道拆解为**检索**和**生成**两个阶段，分别评估：

#### 检索质量 (Retrieval)

| 指标 | 含义 | 公式 | 目标 |
|------|------|------|------|
| **Context Precision** | 检索到的 chunk 中真正相关的比例 | `相关 chunk 数 / 检索总数` | > 0.7 |
| **Context Recall** | 所有相关 chunk 中成功检索到的比例 | `检索到的相关 chunk / 全部相关 chunk` | > 0.7 |
| **Context Relevancy** | 检索内容与问题的语义相关度 | LLM 判断句子级相关度 | > 0.6 |

#### 生成质量 (Generation)

| 指标 | 含义 | 判定方式 | 目标 |
|------|------|------|------|
| **Faithfulness** | 回答是否完全基于检索到的上下文 | 将回答拆解为 claims，逐一验证是否被 context 支撑 | > 0.8 |
| **Answer Relevancy** | 回答是否切题 | 用回答生成反向问题，与原问题比相似度 | > 0.7 |
| **Answer Correctness** | 事实准确性（需 ground truth） | 与标准答案做语义 + TP/FP/FN 比对 | > 0.7 |

### 8.2 项目结构

```
server/evaluation/
  __init__.py
  config.py               # 评估配置（模型、阈值、数据集路径）
  metrics/
    __init__.py
    faithfulness.py        # 忠实度：claims 分解 + 蕴涵判断
    answer_relevancy.py    # 答案相关性：反向问题生成 + 相似度
    context_precision.py   # 上下文精度：逐 chunk 相关性标注
    context_recall.py      # 上下文召回：需 ground truth context
    context_relevancy.py   # 上下文相关性：句子级语义判断
  dataset/
    __init__.py
    test_cases.py          # 手工标注的测试用例（ground truth）
    generator.py           # 自动测试数据生成（从知识库文档合成）
    loader.py              # 从 JSON/YAML 加载数据集
  runner.py                # 评估执行引擎，批量运行 + 汇总报告
  report.py                # 报告生成（Markdown / JSON / HTML）
  api.py                   # 评估 API 端点 (POST /eval/run, GET /eval/report)
  dashboard.py             # CLI 仪表盘 (rich 终端展示)
```

### 8.3 依赖

```toml
# server/pyproject.toml 新增
[project.optional-dependencies]
eval = [
    "ragas>=0.2.0",           # RAGAS 核心
    "datasets>=2.14.0",       # 数据集管理
    "pandas>=2.0.0",          # 结果分析
    "rich>=13.0.0",           # CLI 仪表盘
]
```

### 8.4 测试用例设计

#### 手工标注数据集 (`dataset/test_cases.py`)

```python
# 每个测试用例包含: question, answer, contexts, ground_truth
# 来源: 实际对话日志 + 人工标注

HEALTH_TEST_CASES = [
    {
        "question": "我的空腹血糖是 6.8 mmol/L，需要吃药吗？",
        "answer": "...",               # Agent 实际生成的回答
        "contexts": [                   # search_knowledge 检索到的 chunks
            "空腹血糖正常范围为 3.9-6.1 mmol/L...",
            "空腹血糖 6.1-6.9 mmol/L 属于糖尿病前期...",
        ],
        "ground_truth": "空腹血糖 6.8 mmol/L 属于糖尿病前期（空腹血糖受损），通常不需要立即用药，建议进行 OGTT 检查确认，同时开始生活方式干预：控制饮食、增加运动、减重 5-10%。",
        "category": "体检指标解读",
        "difficulty": "medium",
    },
    # ... 更多用例
]
```

#### 自动生成数据集 (`dataset/generator.py`)

```python
from ragas.testset.generator import TestsetGenerator
from ragas.testset.evolutions import simple, reasoning, multi_context

async def generate_testset(
    documents: list[Document],
    test_size: int = 50,
    distributions: dict = None,  # 各复杂度比例
) -> TestDataset:
    """从知识库文档自动生成测试用例。

    使用 RAGAS 内置的 TestsetGenerator:
    1. 从文档中提取关键段落作为 seed
    2. 对 seed 应用演化策略生成多样化问题:
       - simple: 简单事实型问题
       - reasoning: 需要推理的问题
       - multi_context: 需要跨 chunk 综合的问题
    3. 自动生成 ground_truth answer 和 relevant_contexts
    """
    generator = TestsetGenerator.with_openai(
        generator_llm="deepseek-v4-flash",
        critic_llm="deepseek-v4-flash",
        embeddings=ZhipuAIEmbeddings(),
    )

    return generator.generate_with_langchain_docs(
        documents,
        test_size=test_size,
        distributions=distributions or {
            simple: 0.4,        # 40% 简单事实查询
            reasoning: 0.35,    # 35% 需要推理
            multi_context: 0.25, # 25% 跨文档 / 跨 chunk
        },
    )
```

### 8.5 评估引擎 (`runner.py`)

```python
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
    context_relevancy,
)

class RAGEvaluationRunner:
    """RAGAS 评估执行引擎。

    支持:
      - 单次评估: 对单个 (question, answer, contexts) 打分
      - 批量评估: 对数据集批量运行，生成汇总报告
      - 回归评估: 对比 baseline，标记劣化 > 阈值
      - 增量评估: 仅评估变更相关的用例
    """

    def __init__(
        self,
        llm: BaseChatModel,          # 评估 LLM（建议用强模型）
        embeddings: BaseEmbeddings,   # 语义相似度计算
        metrics: list[Metric] = None,
    ):
        self.llm = llm
        self.embeddings = embeddings
        self.metrics = metrics or [
            faithfulness,
            answer_relevancy,
            context_precision,
            context_recall,
            context_relevancy,
        ]
        self._baseline: dict | None = None  # 回归对比基线

    async def evaluate_single(
        self, question: str, answer: str, contexts: list[str]
    ) -> dict:
        """评估单个 RAG 回答"""
        dataset = Dataset.from_dict({
            "question": [question],
            "answer": [answer],
            "contexts": [contexts],
        })
        result = evaluate(dataset, metrics=self.metrics, llm=self.llm, embeddings=self.embeddings)
        return result.to_pandas().to_dict("records")[0]

    async def evaluate_batch(self, test_cases: list[dict]) -> EvalReport:
        """批量评估，返回结构化报告"""
        ...

    async def regression_test(self, test_cases: list[dict]) -> RegressionResult:
        """回归检测: 与 baseline 对比，标记退化"""
        ...
```

### 8.6 评估 API

```python
# server/evaluation/api.py
from fastapi import APIRouter

eval_router = APIRouter(prefix="/api/eval")

@eval_router.post("/run")
async def run_evaluation(
    dataset_name: str = "default",
    metrics: list[str] | None = None,
) -> EvalReport:
    """手动触发一次评估"""
    ...

@eval_router.get("/report/latest")
async def get_latest_report() -> EvalReport:
    """获取最新评估报告"""
    ...

@eval_router.get("/report/history")
async def get_report_history(limit: int = 10) -> list[EvalReport]:
    """获取历史评估报告列表"""
    ...

@eval_router.post("/baseline")
async def set_baseline(report_id: str) -> dict:
    """将某次评估设为回归基线"""
    ...

@eval_router.get("/regression")
async def check_regression() -> RegressionResult:
    """与基线对比，检查是否退化"""
    ...
```

### 8.7 评估报告示例

```
╔══════════════════════════════════════════════════════════════╗
║           RAGAS Evaluation Report — 2026-07-01               ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  📊 Summary (50 test cases)                                  ║
║  ┌─────────────────────┬────────┬────────┬─────────┐         ║
║  │ Metric              │ Score  │ Target │ Status  │         ║
║  ├─────────────────────┼────────┼────────┼─────────┤         ║
║  │ Faithfulness        │  0.91  │ ≥ 0.80 │  ✅     │         ║
║  │ Answer Relevancy    │  0.83  │ ≥ 0.70 │  ✅     │         ║
║  │ Context Precision   │  0.72  │ ≥ 0.70 │  ✅     │         ║
║  │ Context Recall      │  0.68  │ ≥ 0.70 │  ⚠️ -2% │         ║
║  │ Context Relevancy   │  0.75  │ ≥ 0.60 │  ✅     │         ║
║  └─────────────────────┴────────┴────────┴─────────┘         ║
║                                                              ║
║  ⚠️ Context Recall 未达标 — 建议调整:                         ║
║     - 增加检索 top_k 5→8                                     ║
║     - 降低 score_threshold 1.5→1.8                           ║
║                                                              ║
║  📈 回归对比 (vs baseline 2026-06-28):                        ║
║     Faithfulness: 0.91 → 0.91 (0%)                           ║
║     Context Recall: 0.70 → 0.68 (-2%) ⚠️                    ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

### 8.8 CI/CD 集成

```yaml
# .github/workflows/eval.yml
name: RAG Evaluation

on:
  pull_request:
    paths:
      - 'server/app/rag/**'
      - 'server/app/services/rag_service.py'
      - 'server/app/tools/search_knowledge.py'
  push:
    branches: [main]

jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: cd server && pip install ".[eval]"
      - name: Run RAGAS evaluation
        run: cd server && python -m evaluation.runner
        env:
          DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}
          ZHIPUAI_API_KEY: ${{ secrets.ZHIPUAI_API_KEY }}
      - name: Check regression
        run: cd server && python -m evaluation.runner --regression
      - name: Upload report
        uses: actions/upload-artifact@v4
        with:
          name: eval-report
          path: server/evaluation/reports/
      - name: Comment PR
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v7
        with:
          script: |
            // 在 PR 中自动评论评估结果
            const report = require('./eval-summary.json')
            github.rest.issues.createComment({...})
```

### 8.9 评估触发时机

| 触发条件 | 评估范围 | 阻塞性 |
|------|------|------|
| PR 修改 RAG 相关代码 | 完整测试集 (50+ cases) | ⚠️ Faithfulness < 0.8 阻塞合并 |
| PR 修改其他代码 | 快速冒烟 (10 cases) | 非阻塞，仅报告 |
| 每日定时 (UTC 02:00) | 完整测试集 + 自动生成最新数据集 | 非阻塞，告警 |
| 手动 `/eval/run` | 可选数据集 | 非阻塞 |
| 知识库文档变更后 | 自动生成新测试集 + 旧手工集合并跑 | 非阻塞 |

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
Phase 5: 企业基础 (当前)
  ├── 5.1 容器化 (Docker + docker-compose)              🔴 P0
  ├── 5.2 测试体系 (前端 vitest + 后端 pytest)           🔴 P0
  └── 5.3 API 文档完善 (Swagger + Schema 描述)           🟠 P1

Phase 6: RAGAS 评估体系 ★ 新增
  ├── 6.1 RAGAS 核心指标集成 (5 项指标)                  🔴 P0
  ├── 6.2 手工 + 自动测试数据集                          🔴 P0
  ├── 6.3 评估 API + 报告仪表盘                          🟠 P1
  ├── 6.4 CI/CD 集成 (PR 自动评估 + 回归检测)            🟠 P1
  └── 6.5 评估数据积累 (历史报告 + baseline 管理)        🟡 P2

Phase 7: 生产韧性
  ├── 7.1 结构化日志 + 健康检查增强                       🟠 P1
  ├── 7.2 断路器 + 重试 + Unicode 清理                    🟠 P1
  ├── 7.3 速率限制 + 安全响应头 + 文件上传安全             🟠 P1
  └── 7.4 错误处理体系化 (AppError + 统一响应格式)        🟡 P2

Phase 8: 质量基础设施
  ├── 8.1 后端 lint/format (ruff + mypy)                 🟡 P2
  ├── 8.2 CI/CD (GitHub Actions)                          🟡 P2
  ├── 8.3 功能开关 (config.py)                            🟡 P2
  └── 8.4 缓存层 (Embedding 缓存 + RAG 查询缓存)          🟡 P2

Phase 9: 监控与优化
  ├── 9.1 Prometheus 指标 + 性能监控                      🟠 P1
  └── 9.2 前端架构优化 (虚拟滚动 / 懒加载 / 错误边界)     🟢 P3

Phase 10: 锦上添花
  ├── 10.1 国际化 (vue-i18n)                               🟢 P3
  └── 10.2 多 Agent 协作 (适用场景评估后决定)               🟢 P3
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

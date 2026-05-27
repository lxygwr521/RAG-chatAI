# 上下文管理 — 滚动摘要方案（Rolling Summary）

## Context

当前项目在 [chat.vue:165-180](src/pages/chat.vue#L165-L180) 的 `buildLLMMessages` 中将**全部历史消息**拼接到每次 API 请求中，没有任何截断或限制。随着对话增长会导致：
- 超出 DeepSeek-v4 的 128K 上下文窗口，API 报错或服务端静默截断
- 请求体越来越大，网络延迟增加
- localStorage 存储膨胀

本方案采用**滚动摘要**策略：当历史消息超过阈值时，自动将早期对话压缩为一段摘要，构建"系统提示 + 摘要 + 近期消息 + 当前问题"的上下文结构，兼顾长期记忆和近期精确度。

## 技术架构

```
发送消息
    │
    ▼
┌─────────────────────┐
│  估算全量 token      │  ← src/utils/token.ts (NEW)
└──────┬──────────────┘
       │
       ├── 未超阈值 ──→ 直接使用全部历史
       │
       └── 超阈值 ──→ ┌──────────────────────┐
                      │  分离早期 / 近期消息    │
                      │  调用摘要 API（非流式） │  ← src/utils/context.ts (NEW)
                      │  合并旧摘要 → 新摘要    │
                      │  持久化摘要到 store     │
                      └──────┬───────────────┘
                             │
                             ▼
              [系统提示] + [摘要] + [近期消息] + [当前问题]
```

## 分步实现

### Step 1: 新增 token 估算工具 `src/utils/token.ts`

- 导出 `estimateTokens(text: string): number`
- 使用字符比例估算：中文约 1.5 字符/token，英文约 4 字符/token，取保守值 `Math.ceil(text.length / 2.5)`
- 如果后续需要更精确估算，可替换为 `gpt-tokenizer` 库（纯 JS，支持浏览器），但当前字符估算已足够保护上下文窗口

### Step 2: 新增上下文管理模块 `src/utils/context.ts`

导出以下核心函数：

**2.1 `buildContext(params): Promise<LLMMessage[]>`**

参数：
```typescript
interface ContextParams {
  systemPrompt: string
  history: Array<{ role: string; content: string }>
  userContent: string
  existingSummary?: string         // 已有的累积摘要
  summaryUpToIndex?: number        // 摘要已覆盖到第几条消息
}
```

返回值：可直接传给 `callLLM` 的 messages 数组。

逻辑流程：
1. 计算全量 token 数（system + history + userContent）
2. 若 `totalTokens <= MAX_CONTEXT_TOKENS`（默认 80000）：直接返回 `[system, ...history, user]`，如果有已有摘要则插入 system 之后
3. 若超阈值：
   - 保留最近 `RECENT_WINDOW_SIZE`（默认 10 对 = 20 条）消息不动
   - 早期消息 = 已有摘要未覆盖的部分（从 `summaryUpToIndex` 到 `history.length - RECENT_WINDOW_SIZE`）
   - 调用 `generateSummary(existingSummary, earlyMessages)` 生成合并摘要
   - 返回 `[system, { role: 'system', content: summaryPrompt }, ...recentMessages, user]`

**2.2 `generateSummary(existingSummary, newMessages): Promise<{ summary: string }>`**

- 使用 `fetch` 直接调用 DeepSeek API，**非流式**（`stream: false`）
- 摘要 prompt 模板：
  ```
  你是一个对话摘要助手。请将以下对话内容压缩为简洁的摘要（200字以内），
  保留所有关键事实、用户偏好、重要决策和待办事项。

  [已有摘要]
  ${existingSummary || '无'}

  [新对话内容]
  ${formattedNewMessages}

  请输出合并后的完整摘要：
  ```
- 设置 `max_tokens: 400` 控制摘要长度
- 返回摘要文本

**2.3 配置常量**

```typescript
const MAX_CONTEXT_TOKENS = 80000      // 预留 ~48K 给回复和 reasoning
const RECENT_WINDOW_SIZE = 20         // 始终完整保留最近 20 条消息
const SUMMARY_TOKEN_BUFFER = 1000     // 摘要 prompt 自身的 token 开销
```

### Step 3: 修改 Message Store `src/stores/conversation.ts`

在 `useMessageStore` 中新增摘要状态管理：

```typescript
// 每个会话的摘要状态
const summaryMap = reactive<Record<string, {
  text: string          // 累积摘要文本
  upToIndex: number     // 该摘要覆盖到了 messageMap[id] 中的第几条（索引）
}>>({})

function getSummary(convId: string) { ... }
function setSummary(convId: string, text: string, upToIndex: number) { ... }
function clearSummary(convId: string) { ... }
```

摘要状态随 `persist` 插件自动存入 localStorage，无需额外配置。

### Step 4: 修改 `src/api/llm.ts`

**4.1 Payload 增加字段**

```typescript
interface Payload {
  model: string
  messages: LLMMessage[]
  stream?: boolean         // 已有
  max_tokens?: number      // 新增：限制回复长度
  thinking?: { type: ThinkingType }   // 已有
  reasoning_effort?: ReasoningEffort  // 已有
}
```

**4.2 新增 `summarizeMessages` 导出函数**

```typescript
async function summarizeMessages(
  existingSummary: string,
  newMessages: LLMMessage[]
): Promise<string>
```

独立的非流式 API 调用，用于摘要生成。参数与 `callLLM` 解耦，避免影响主流程。

### Step 5: 修改 `src/pages/chat.vue` — 接入上下文管理

**5.1 重写 `buildLLMMessages`**

将原来的简单拼接改为调用 `context.ts` 的 `buildContext`：

```typescript
async function buildLLMMessages(
  question: string, 
  files: UploadFile[]
): Promise<LLMMessage[]> {
  const history = currentMessages.value.map(msg => ({
    role: msg.role,
    content: msg.content
  }))
  const userContent = await buildUserContent(question, files)
  const convId = conversationStore.currentConversationId!
  const summaryState = messageStore.getSummary(convId)

  const { messages, newSummary } = await buildContext({
    systemPrompt: SYSTEM_MESSAGE.content,
    history,
    userContent,
    existingSummary: summaryState?.text,
    summaryUpToIndex: summaryState?.upToIndex
  })

  // 持久化更新后的摘要
  if (newSummary) {
    const recentStartIndex = history.length - RECENT_WINDOW_SIZE
    const oldCovered = summaryState?.upToIndex ?? 0
    messageStore.setSummary(convId, newSummary.text, oldCovered + newSummary.coveredCount)
  }

  return messages
}
```

**5.2 发送流程中处理摘要更新的 timing**

摘要 API 调用是异步的，会额外增加 ~1-2 秒延迟。需要：
- 在 `handleSend` 中，`buildLLMMessages` 变为 async，结果等待完成后再调用 `callLLM`
- 摘要调用期间用户已经在等待（这是合理的，因为不摘要的话请求也会变慢甚至失败）

### Step 6: 处理边界情况

1. **新建会话**：无历史消息，不做任何摘要
2. **摘要 API 失败**：降级为滑窗截断（只保留最近消息，丢弃早期消息），确保主流程不中断
3. **摘要被 localStorage 清除**：`existingSummary` 为 undefined，重新全量摘要
4. **用户清空消息**：同时清除对应 `summaryMap` 条目
5. **思考模式**：`deepseek-think` 的 reasoning tokens 额外占窗口，考虑将 `MAX_CONTEXT_TOKENS` 调低至 60000

## 涉及文件

| 文件 | 操作 | 说明 |
|------|------|------|
| [src/utils/token.ts](src/utils/) | **新建** | token 估算工具 |
| [src/utils/context.ts](src/utils/) | **新建** | 上下文构建 + 摘要生成 |
| [src/stores/conversation.ts](src/stores/conversation.ts) | 修改 | 增加 summaryMap 状态和持久化 |
| [src/api/llm.ts](src/api/llm.ts) | 修改 | Payload 加 max_tokens + 新增 summarizeMessages |
| [src/pages/chat.vue](src/pages/chat.vue) | 修改 | buildLLMMessages 接入 context 管理 |

## 验证方法

1. **短对话测试**：新建会话，发送 3-5 轮对话，确认行为与修改前一致（不触发摘要）
2. **长对话触发摘要**：手动在 localStorage 写入 30+ 条历史消息，发送新消息，确认：
   - Network 面板出现一次非流式的 `/chat/completions` 摘要请求
   - 主请求的 messages 中包含摘要 system message
3. **摘要降级测试**：断开网络 → 发送消息 → 确认降级为滑窗截断，不会白屏或报错
4. **持久化测试**：摘要完成后刷新页面，确认 `summaryMap` 仍在 localStorage 中，后续请求复用已有摘要
5. **跨会话隔离**：创建两个对话，确认各自的摘要互不干扰

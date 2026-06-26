# 增量 Markdown 解析优化方案

## Context

当前流式输出期间，[AssistantMsg.vue:18-24](src/components/chat/AssistantMsg.vue#L18-L24) 的 RAF watch 每帧调用 `renderMarkdownText(fullContent)`，对已累积的全部文本做完整的三阶段处理：

```
renderMarkdownText(content)
  ├── transformThinkMarkdown(content)   ← O(n) 逐字符扫描 + 每字符 2 次 slice()
  ├── transformMathMarkdown(content)    ← KaTeX splitAtDelimiters 全量扫描
  └── md.render(content)               ← markdown-it + highlight.js + KaTeX 全量解析
```

一条 4000 字符的回复≈4 秒流式输出≈240 帧。平均每帧处理 2000 字符，总计处理 ≈480,000 字符的 markdown，其中 `transformThinkMarkdown` 的 `slice(i, i+7)` 和 `slice(i, i+8)` 每帧产生约 4000 次字符串分配。

## 优化策略

分两步走：

### Step 1: 优化 `transformThinkMarkdown` — 消除逐字符 slice

**问题**：[markdown.ts:88-90](src/utils/markdown.ts#L88-L90) 每字符调用两次 `slice()`：

```typescript
const nextChars = source.slice(i, i + 7)  // 每字符创建一个 7 字符子串
const endChars = source.slice(i, i + 8)   // 每字符创建一个 8 字符子串
```

4000 字符 = 8000 次 slice 分配，240 帧 = 192 万次 slice。

**方案**：改为直接逐字符下标比较，零分配：

```typescript
// 替换 slice 比较：
// source[i..i+6] === '<think>'
source[i] === '<' && source[i+1] === 't' && source[i+2] === 'h' &&
source[i+3] === 'i' && source[i+4] === 'n' && source[i+5] === 'k' && source[i+6] === '>'

// source[i..i+7] === '</think>'
source[i] === '<' && source[i+1] === '/' && source[i+2] === 't' &&
source[i+3] === 'h' && source[i+4] === 'i' && source[i+5] === 'n' &&
source[i+6] === 'k' && source[i+7] === '>'
```

另外循环可以限制范围，`<think>` 只需要检查到 `source.length - 7`：

```typescript
for (let i = 0; i < source.length; i++) {
  const char = source[i]

  if (!inThinkBlock && i <= source.length - 7 &&
      source[i] === '<' && source[i+1] === 't' && ... && source[i+6] === '>') {
    // ...
    i += 6
    continue
  }
  // ...
}
```

**效果**：消除每帧数千次字符串分配，`transformThinkMarkdown` 变为纯字符遍历。

---

### Step 2: 自适应频次渲染器

**问题**：流式期间每帧都全量重渲染，但用户无法感知 16ms 的内容变化。内容越长，每次渲染越贵，但渲染频率完全没变。

**方案**：新建 `createStreamingRenderer()` 工厂函数，根据内容长度自适应降低渲染频次：

```
内容长度 < 500 字符  → 每增长 30 字符或每 80ms 渲染一次  (频繁,保证打字机顺滑)
内容 500~2000 字符  → 每增长 80 字符或每 150ms 渲染一次
内容 > 2000 字符    → 每增长 150 字符或每 300ms 渲染一次  (稀疏,节省 CPU)
```

同时内建结果缓存：内容未变化时直接返回缓存的 HTML，零开销。

### 新增 `createStreamingRenderer()` in `src/utils/markdown.ts`

```typescript
export function createStreamingRenderer() {
  let lastContent = ''
  let lastHtml = ''
  let lastRenderTime = 0
  let lastRenderLength = 0

  return (content: string): string => {
    // 内容未变化 → 缓存命中
    if (content === lastContent) return lastHtml

    const now = performance.now()
    const growth = content.length - lastRenderLength
    const elapsed = now - lastRenderTime

    // 自适应节流参数
    const len = content.length
    const minGrowth = len < 500 ? 30 : len < 2000 ? 80 : 150
    const minInterval = len < 500 ? 80 : len < 2000 ? 150 : 300

    if (growth < minGrowth && elapsed < minInterval) {
      return lastHtml  // 跳过，返回上次结果
    }

    lastContent = content
    lastRenderTime = now
    lastRenderLength = content.length
    lastHtml = renderMarkdownText(content)
    return lastHtml
  }
}
```

### 修改 `src/components/chat/AssistantMsg.vue`

```typescript
import { createStreamingRenderer } from '@/utils/markdown'

const renderer = createStreamingRenderer()

// watch 中：
watch(rawContent, (val) => {
  if (rafId !== null) return
  rafId = requestAnimationFrame(() => {
    displayedContent.value = renderer(val)
    rafId = null
  })
}, { immediate: true })
```

**效果**：

| 场景 | 优化前 | 优化后 |
|------|--------|--------|
| 4000 字符回复渲染次数 | ~240 帧 | ~30-40 次 |
| transformThinkMarkdown 分配 | 192 万次 slice | 0 |
| 已完成消息重新渲染 | 每次重渲染都重新解析 | 命中缓存，直接返回 |

> `createStreamingRenderer` 是 per-component 实例。消息完成后 `content` 不再变化，后续任何触发都命中 `content === lastContent` 直接返回缓存 HTML，零开销。

---

## 涉及文件

| 文件 | 操作 | 说明 |
|------|------|------|
| [src/utils/markdown.ts](src/utils/markdown.ts) | 修改 | 优化 think 标签检测 + 新增 createStreamingRenderer |
| [src/components/chat/AssistantMsg.vue](src/components/chat/AssistantMsg.vue) | 修改 | 使用 createStreamingRenderer 替代直接调用 |

## 验证方法

1. **功能回归**：发送包含 `<think>` 标签、数学公式 `$$x^2$$`、代码块的消息，确认渲染结果与优化前完全一致
2. **性能对比**：在 Performance 面板录制同一段长回复的流式输出，对比优化前后的 `renderMarkdownText` 调用次数和总耗时
3. **缓存验证**：流式完成后，切换对话再切回来，确认旧消息的 `renderMarkdownText` 不再被调用（DevTools 断点验证）

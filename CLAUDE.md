# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Vue 3 AI chat application (ChatGPT-style) built with Vite + TypeScript. Supports streaming responses from DeepSeek models with conversation management, file uploads, markdown rendering, and automatic context compression.

## Commands

```bash
pnpm dev          # Start dev server on port 3000 (proxies /api → localhost:3001)
pnpm build        # Type-check then production build
pnpm preview      # Preview production build
pnpm type-check   # Run vue-tsc --noEmit
pnpm lint         # Run both oxlint and eslint (auto-fix)
```

There are no tests yet.

## Architecture

### State Management (Pinia)

Two persisted stores in [src/stores/conversation.ts](src/stores/conversation.ts):

- **`useConversationStore`** — manages `Conversation[]` metadata (id, title, model, createdAt). Persisted to `localStorage` under key `chat-conversations`.
- **`useMessageStore`** — manages a `Record<string, Message[]>` keyed by conversation ID, plus a `summaryMap` for incremental context compression state. Persisted via `debouncedLocalStorage` (500ms debounce) under key `chat-messages` to avoid excessive writes during streaming.

Both use `pinia-plugin-persistedstate`. The message store uses `reactive()` (not `ref()`) for the message/summary maps so nested mutations trigger reactivity during streaming updates.

### Data Flow

1. [chat.vue](src/pages/chat.vue) handles user input → creates/updates conversation → adds `UserMessage` to store → calls `buildLLMMessages()`.
2. `buildLLMMessages()` (in chat.vue) converts store messages to LLM format, then calls `buildContext()` from [src/utils/context/context.ts](src/utils/context/context.ts).
3. `buildContext()` checks if total tokens exceed 80K threshold. If so, it calls the DeepSeek API to summarize older messages while keeping the 20 most recent messages verbatim. Summary result is persisted back to `messageStore.setSummary()`.
4. The resulting `LLMMessage[]` is sent to `callLLM()` in [src/api/llm.ts](src/api/llm.ts), which streams SSE responses through a `TransformStream` pipeline.
5. [chat.vue](src/pages/chat.vue) reads the stream, handling `<think>` tags (reasoning content) separately from normal content, and progressively appends to an `AssistantMessage` in the store.

### Context Compression ("增量压缩")

[src/utils/context/context.ts](src/utils/context/context.ts) implements incremental summarization:
- Token estimation via `estimateTokens()` in [src/utils/context/token.ts](src/utils/context/token.ts) (simple `Math.ceil(len / 2.5)` heuristic).
- When total tokens exceed `MAX_CONTEXT_TOKENS` (80K), messages are split: the most recent 20 are kept verbatim; older unsummarized messages are sent to DeepSeek's flash model for summarization.
- Summaries are cumulative — each new summary merges with the previous one via the API prompt.
- Falls back to simple window truncation if the summary API fails.

### Message Types

Defined in [src/components/chat/types.ts](src/components/chat/types.ts):
- `Message = UserMessage | AssistantMessage`
- `UserMessage`: `{ role: 'user', content, timestamp, files?: UploadFile[] }`
- `AssistantMessage`: `{ role: 'assistant', content, thinkingContent?, timestamp }`
- Separate `UserMessageProps`/`AssistantMessageProps` types are used by components (no `role` field needed — the component already knows its side).

### SSE Stream Processing

[src/utils/transform.ts](src/utils/transform.ts) implements a `TransformStream` that:
1. Buffers incoming chunks.
2. Detects SSE format (`data:` prefix) or raw JSON format.
3. Splits on `\n`, extracts complete JSON objects, and enqueues them for the reader.
4. Handles partial chunks across buffer boundaries.

### Markdown Rendering

[src/utils/markdown.ts](src/utils/markdown.ts) renders assistant responses:
- `transformThinkMarkdown()` — wraps `<think>...</think>` content in a `<div class="think-wrapper">`, escapes `<script>` tags for XSS safety.
- `transformMathMarkdown()` — converts `\(` / `\[` LaTeX delimiters to `$` / `$$` format.
- Uses `markdown-it` with highlight.js (GitHub theme) and KaTeX for math.

### Vite Configuration

- **Path alias**: `@` → `src/`
- **SCSS**: `_variables.scss` is auto-injected into every SCX `<style>` block via `additionalData`, along with `@use "sass:color"`.
- **Auto-import**: Vue/Pinia APIs and Naive UI composables (`useDialog`, `useMessage`, `useNotification`, `useLoadingBar`) are auto-imported. Naive UI components are auto-resolved.
- **Raw imports**: `.md` files are imported as strings via `vite-raw-plugin` (used for mock streaming data).
- **Dev proxy**: `/api` → `http://localhost:3001`

### Key Dependencies

- UI framework: Naive UI (`naive-ui`)
- Styling: Tailwind CSS 4 + SCSS (modules), with design tokens in `_variables.scss`
- State: Pinia with `pinia-plugin-persistedstate`
- Markdown: `markdown-it` + `highlight.js` + `katex`
- Linting: oxlint (primary, fast) + eslint (secondary)

## TypeScript Rules (from .cursor/rules)

- Business types go in `.ts` files, NOT `.d.ts`.
- `.d.ts` is only for globals (`declare global`), third-party augmentation, and env var declarations.
- Vue props must be explicitly typed.
- **Do not delete any comments.**

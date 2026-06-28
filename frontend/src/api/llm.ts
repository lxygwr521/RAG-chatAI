import * as TransformUtils from '@/utils/transform'
import { useConversationStore } from '../stores/conversation'

// LLMMessage format — the role+content pair sent to the LLM
interface LLMMessage {
  role: string
  content: string
}

// Chat request payload sent to POST /api/chat
interface ChatRequest {
  conversation_id?: string
  model: string
  messages: LLMMessage[]
  use_rag?: boolean
  files?: { id: string; filename: string }[]
}

/**
 * Call the backend chat API, which proxies to DeepSeek (or serves mock).
 * Returns a reader that yields individual SSE data strings,
 * exactly like the old direct-DeepSeek flow.
 *
 * The SSE data format is DeepSeek-compatible:
 *   {"choices":[{"delta":{"content":"...","reasoning_content":"..."}}]}
 * The first event may be {"conversation_id":"..."} for new conversations.
 */
async function callLLM(
  messages: LLMMessage[],
  controller?: AbortController,
  options?: { useRag?: boolean; files?: { id: string; filename: string }[] }
): Promise<{ error: number; reader: ReadableStreamDefaultReader<string> | null }> {
  const conversationStore = useConversationStore()

  const payload: ChatRequest = {
    conversation_id: conversationStore.currentConversationId ?? undefined,
    model: conversationStore.selectedModel,
    messages,
    use_rag: options?.useRag ?? false,
    files: options?.files,
  }

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: controller?.signal,
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    if (response.body) {
      const reader = response.body
        .pipeThrough(new TextDecoderStream())
        // Same SSE parser as before — splits on \n, handles data: prefix
        .pipeThrough(TransformUtils.splitStream('\n'))
        .getReader()
      return { error: 0, reader: reader as ReadableStreamDefaultReader<string> }
    }

    return { error: 1, reader: null }
  } catch (err) {
    if ((err as Error).name === 'AbortError') {
      return { error: 0, reader: null }
    }
    console.error('Chat API error:', err)
    return { error: 1, reader: null }
  }
}

export { type LLMMessage }
export default callLLM

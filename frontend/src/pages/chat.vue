<template>
  <div class="chat-page flex h-screen bg-white">
    <div class="chat-main-wrapper flex flex-col flex-1 min-w-0">
      <!-- 聊天主区域 -->
      <main class="chat-main flex-1 overflow-y-auto" ref="chatMainRef">
        <div class="chat-messages flex flex-col min-h-full py-4 px-5 md:px-8">
          <template v-if="currentMessages.length !== 0">
            <div
              v-for="msg in currentMessages"
              :key="msg.timestamp"
              v-memo="[msg.content]"
              :ref="el => setMsgRef(msg.timestamp, el as HTMLElement)"
              :data-msg-ts="msg.timestamp"
            >
            <UserMsg
              v-if="msg.role === 'user'"
              :message="{ content: msg.content, timestamp: msg.timestamp, files: msg.files }"
              class="animate-message"
            />
            <AssistantMsg
              v-else
              :message="{ content: msg.content, timestamp: msg.timestamp, citations: msg.citations }"
              class="animate-message"
              style="width: 100%;"
            />
            </div>
               <!-- 底部占位，确保新消息在可视区域 -->
            <div class="h-10 shrink-0" />
          </template>
          <template v-else>
            <NoData />
            <QuickQuestions
              :questions="quickQuestions"
              @select="handleQuickQuestion"
            />
          </template>
        </div>
      </main>

      <!-- 输入区域 -->
      <ChatInput
        :is-generating="isGenerating"
        @submit="handleSend"
        @stop="handleStop"
      />
    </div>

    <!-- 对话记录导航栏 -->
    <ChatNav
      :messages="currentMessages"
      :active-index="activeNavIndex"
      @scroll-to="scrollToMessage"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, nextTick, watch, onMounted, onBeforeUnmount } from 'vue'
import callLLM, { type LLMMessage } from '@/api/llm'
import { useConversationStore, useMessageStore } from '@/stores/conversation'
import UserMsg from '@/components/chat/UserMsg.vue'
import AssistantMsg from '@/components/chat/AssistantMsg.vue'
import ChatInput from '@/components/chat/ChatInput.vue'
import ChatNav from '@/components/chat/ChatNav.vue'
import QuickQuestions from '@/components/chat/QuickQuestions.vue'
import type { UserMessage, AssistantMessage, UploadFile, Citation } from '@/components/chat/types'
import NoData from '@/components/noData.vue'

const conversationStore = useConversationStore()
const messageStore = useMessageStore()

// Quick questions for empty state
const quickQuestions = [
  '如何学习 Vue 3？',
  'Tailwind CSS 和 SCSS 有什么区别？',
  '什么是 Composition API？',
]

// 当前会话的消息列表
const currentMessages = computed(() => {
  const id = conversationStore.currentConversationId
  if (!id) return []
  return messageStore.getMessages(id)
})

const chatMainRef = ref<HTMLElement | null>(null)
const isGenerating = ref(false)
// useMock is no longer needed — mock mode is handled server-side
// const useMock = computed(() => conversationStore.selectedModel === 'mock')

// 消息 DOM 引用，用于导航跳转
const msgRefMap = new Map<number, HTMLElement>()
function setMsgRef(timestamp: number, el: HTMLElement | null) {
  if (el) {
    msgRefMap.set(timestamp, el)
    observer?.observe(el)
  } else {
    msgRefMap.delete(timestamp)
  }
}

// 当前可见消息索引，用于导航高亮
const activeNavIndex = ref(-1)
let observer: IntersectionObserver | null = null

function scrollToMessage(timestamp: number) {
  const el = msgRefMap.get(timestamp)
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}

onMounted(() => {
  //监听消息元素是否进入聊天区域视口。
  observer = new IntersectionObserver(
    entries => {
      let closestIdx = -1
      let minTop = Infinity
      entries.forEach(entry => {
        const el = entry.target as HTMLElement
        const ts = Number(el.dataset.msgTs)
        if (entry.isIntersecting && entry.boundingClientRect.top < minTop) {
          minTop = entry.boundingClientRect.top
          closestIdx = currentMessages.value.findIndex(m => m.timestamp === ts)
        }
      })
      if (closestIdx !== -1) {
        activeNavIndex.value = closestIdx
      }
    },
    { root: chatMainRef.value, rootMargin: '-40px 0px -60% 0px', threshold: 0 }
  )

  // 观察已有消息元素
  msgRefMap.forEach(el => {
    observer!.observe(el)
  })
})

onBeforeUnmount(() => {
  observer?.disconnect()
})

let currentReader: ReadableStreamDefaultReader<string> | null = null
let currentController: AbortController | null = null
const textBuffer = ref('')

// 自动滚动到底部
function scrollToBottom() {
  nextTick(() => {
    if (chatMainRef.value) {
      chatMainRef.value.scrollTop = chatMainRef.value.scrollHeight
    }
  })
}

// 监听消息变化，自动滚动
watch(currentMessages, () => {
  scrollToBottom()
}, { deep: true })

// 生成会话标题（取首条用户消息前20字）
function generateTitle(question: string): string {
  const text = question.trim()
  if (text.length <= 20) return text
  return text.substring(0, 20) + '...'
}

// 初始化系统消息
const SYSTEM_MESSAGE = { role: 'system', content: 'You are a helpful assistant.' }

// 读取聊天附件的文本内容
async function readChatFiles(files: UploadFile[]): Promise<string> {
  const results = await Promise.all(
    files.map(
      item =>
        new Promise<string>((resolve, reject) => {
          const reader = new FileReader()
          reader.onload = () => resolve(reader.result as string)
          reader.onerror = () => reject(new Error(`读取文件失败: ${item.file.name}`))
          reader.readAsText(item.file)
        })
    )
  )
  return results
    .map((content, i) => {
      const { name } = files[i]!.file
      return `[文件: ${name}]\n${content}`
    })
    .join('\n\n')
}

// 将 store 中的消息转换为 LLM API 格式
// 聊天附件读取后嵌入用户消息内容，知识库文档由后端 RAG 检索
async function buildLLMMessages(question: string, files: UploadFile[]): Promise<LLMMessage[]> {
  const history: LLMMessage[] = currentMessages.value.map(msg => ({
    role: msg.role,
    content: msg.content,
  }))

  // 构建用户消息内容，包含聊天附件
  let userContent = question
  if (files && files.length > 0) {
    try {
      const fileContent = await readChatFiles(files)
      userContent = `${fileContent}\n\n---\n\n${question}`.trim()
    } catch (e) {
      console.error('读取聊天附件失败:', e)
    }
  }

  const messages: LLMMessage[] = [SYSTEM_MESSAGE, ...history]
  messages.push({ role: 'user', content: userContent })
  return messages
}

async function handleSend(question: string, files?: UploadFile[], useRag?: boolean) {
  // 确保当前有激活的会话
  if (!conversationStore.currentConversationId) {
    conversationStore.createConversation()
  }

  const _useRag = useRag ?? false

  const convId = conversationStore.currentConversationId!
  const conv = conversationStore.conversations.find(c => c.id === convId)

  // 如果是新建空白会话，生成标题
  if (conv && conv.title === '新对话' && currentMessages.value.length === 0) {
    conversationStore.updateConversationTitle(convId, generateTitle(question))
  }

  const userMsg: UserMessage = {
    role: 'user',
    content: question,
    timestamp: Date.now(),
    files,
  }
  messageStore.addMessage(convId, userMsg)
  isGenerating.value = true

  currentController = new AbortController()

  const messages = await buildLLMMessages(question, files ?? [])

  callLLM(messages, currentController ?? undefined, { useRag: _useRag }).then(async res => {
    if (currentController?.signal.aborted) return

    if (res.reader) {
      currentReader = res.reader
      const reader = currentReader
      const assistantMsg = reactive<AssistantMessage>({
        role: 'assistant',
        content: '',
        thinkingContent: '',
        timestamp: Date.now(),
      })
      messageStore.addMessage(convId, assistantMsg)

      let isThinking = false
      // Track tool calls for intermediate display
      const toolCalls: { tool_call_id: string; tool_name: string; arguments: Record<string, unknown>; result?: string; success?: boolean }[] = []

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        if (!value) continue

        // Check raw [DONE] sentinel (backward compat)
        if (typeof value === 'string' && value.trim() === '[DONE]') break

        try {
          const parsed = JSON.parse(value)

          // === Typed SSE events (Phase 2+) ===
          let eventType: string | null = null
          let eventData: unknown = null

          if (parsed.event && parsed.data) {
            // Typed event: {"event": "delta", "data": "{...}"}
            eventType = parsed.event as string
            eventData = typeof parsed.data === 'string' ? JSON.parse(parsed.data) : parsed.data
          } else {
            // Raw format (backward compat): {"choices":[...]} or {"citations":[...]}
            eventData = parsed
          }

          // Handle done event
          if (eventType === 'done' || (typeof eventData === 'object' && (eventData as Record<string, unknown>)?.done)) {
            break
          }

          // Handle [DONE] inside data
          if (typeof eventData === 'string' && (eventData as string).trim() === '[DONE]') break

          const data = eventData as Record<string, unknown>

          // Handle citations (RAG sources)
          if (data.citations) {
            assistantMsg.citations = data.citations as Citation[]
            continue
          }

          // Handle tool_call event
          if (eventType === 'tool_call' || data.tool_call_id) {
            const tc = data as { tool_call_id: string; tool_name: string; arguments: Record<string, unknown> }
            toolCalls.push({ tool_call_id: tc.tool_call_id, tool_name: tc.tool_name, arguments: tc.arguments })
            // Store in assistantMsg for display
            ;(assistantMsg as unknown as Record<string, unknown>)._toolCalls = toolCalls
            continue
          }

          // Handle tool_result event
          if (eventType === 'tool_result' || (data.tool_call_id && data.result !== undefined)) {
            const tr = data as { tool_call_id: string; tool_name: string; result: string; success: boolean }
            const existingCall = toolCalls.find(tc => tc.tool_call_id === tr.tool_call_id)
            if (existingCall) {
              existingCall.result = tr.result
              existingCall.success = tr.success
            }
            ;(assistantMsg as unknown as Record<string, unknown>)._toolCalls = toolCalls
            continue
          }

          // Handle error event
          if (eventType === 'error') {
            assistantMsg.content += `\n\n> ⚠️ 错误: ${(data as { error: string }).error}`
            continue
          }

          const thinkingContent = (data as { choices?: [{ delta?: { reasoning_content?: string; content?: string | null } }] }).choices?.[0]?.delta?.reasoning_content
          const content = (data as { choices?: [{ delta?: { reasoning_content?: string; content?: string | null } }] }).choices?.[0]?.delta?.content

          // 开始处理推理过程
          if (content === null && thinkingContent) {
            if (!isThinking) {
              textBuffer.value += '<think>'
              isThinking = true
            }
            textBuffer.value += thinkingContent
          }
          // 当 content 出现时，说明推理结束
          else if (content !== null && !thinkingContent) {
            if (isThinking) {
              textBuffer.value += '</think> \n\n'
              isThinking = false
            }
            textBuffer.value += content
          }
          if (textBuffer.value.length > 0) {
            const nextChunk = textBuffer.value.substring(0, 10)
            assistantMsg.content += nextChunk
            textBuffer.value = textBuffer.value.substring(10)
          }
        } catch {
          // 非 JSON 数据跳过
        }
      }

      isGenerating.value = false
      currentReader = null
      currentController = null
    }
  }).catch(err => {
    console.error(err)
    isGenerating.value = false
    currentReader = null
    currentController = null
  })
}

function handleStop() {
  currentController?.abort()
  currentController = null
  if (currentReader) {
    currentReader.cancel()
    currentReader = null
  }
  isGenerating.value = false
}

function handleQuickQuestion(question: string) {
  if (isGenerating.value) return
  if (!conversationStore.currentConversationId) {
    conversationStore.createConversation()
  }
  handleSend(question)
}
</script>

<style scoped lang="scss">
// 消息入场动画
@keyframes messageIn {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.animate-message {
  animation: messageIn 0.3s ease-out;
}

// 暗色模式支持
:global(.dark) {
  .chat-page {
    background: $color-bg-dark;
  }

  .chat-main {
    background: $color-bg-dark-secondary;
  }
}
</style>

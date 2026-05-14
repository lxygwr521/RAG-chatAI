<template>
  <div class="chat-page flex flex-col h-screen bg-white">
    <!-- 聊天主区域 -->
    <main class="chat-main flex-1 overflow-y-auto" ref="chatMainRef">
      <div class="chat-messages flex flex-col min-h-full py-4 px-5 md:px-8">
        <template v-if="currentMessages.length !== 0">
          <template
            v-for="msg in currentMessages"
            :key="msg.timestamp"
          >
          <UserMsg
            v-if="msg.role === 'user'"
            :message="{ content: msg.content, timestamp: msg.timestamp, files: msg.files }"
            class="animate-message"
          />
          <AssistantMsg
            v-else
            :message="{ content: msg.content, timestamp: msg.timestamp }"
            class="animate-message"
            style="width: 100%;"
          />
          </template>
             <!-- 底部占位，确保新消息在可视区域 -->
          <div class="h-10 shrink-0" />
        </template>
        <template v-else>
          <NoData />
          <QuickQuestions
            :questions="mockQuestions"
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
</template>

<script setup lang="ts">
import { ref, reactive, computed, nextTick, watch } from 'vue'
import callLLM, { buildUserContent } from '@/api/llm'
import { useConversationStore, useMessageStore } from '@/stores/conversation'
import UserMsg from '@/components/chat/UserMsg.vue'
import AssistantMsg from '@/components/chat/AssistantMsg.vue'
import ChatInput from '@/components/chat/ChatInput.vue'
import QuickQuestions from '@/components/chat/QuickQuestions.vue'
import { mockQuestions, mockEventStreamText } from '@/mock'
import type { UserMessage, AssistantMessage, UploadFile } from '@/components/chat/types'
import NoData from '@/components/noData.vue'

const conversationStore = useConversationStore()
const messageStore = useMessageStore()

// 当前会话的消息列表
const currentMessages = computed(() => {
  const id = conversationStore.currentConversationId
  if (!id) return []
  return messageStore.getMessages(id)
})

const chatMainRef = ref<HTMLElement | null>(null)
const isGenerating = ref(false)
const useMock = computed(() => conversationStore.selectedModel === 'mock')

let mockInterval: ReturnType<typeof setInterval> | null = null
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

// 将 store 中的消息转换为 LLM API 格式
function buildLLMMessages(question: string, files: UploadFile[]): Promise<Array<{ role: string; content: string }>> {
  const history = currentMessages.value.map(msg => ({
    role: msg.role,
    content: msg.content
  }))

   
  return buildUserContent(question, files).then(userContent => {
    const messages = [
      SYSTEM_MESSAGE,
      ...history,
      { role: 'user', content: userContent }
    ]
    return messages
  })
}

function handleSend(question: string, files?: UploadFile[]) {
  // 确保当前有激活的会话
  if (!conversationStore.currentConversationId) {
    conversationStore.createConversation()
  }

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
    files
  }
  messageStore.addMessage(convId, userMsg)
  isGenerating.value = true

  if (useMock.value) {
    simulateMockResponse(convId)
    return
  }

  currentController = new AbortController()

  buildLLMMessages(question, files ?? []).then(async messages => {
    if (currentController?.signal.aborted) return

    const res = await callLLM(messages, currentController ?? undefined)

    if (res.reader) {
      currentReader = res.reader
      const reader = currentReader
      const assistantMsg = reactive<AssistantMessage>({
        role: 'assistant',
        content: '',
        thinkingContent: '',
        timestamp: Date.now()
      })
      messageStore.addMessage(convId, assistantMsg)
      let isThinking = false
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        if (!value) continue
        if (value.trim() === '[DONE]') break

        try {
          const data = JSON.parse(value)
          const thinkingContent = data.choices?.[0]?.delta?.reasoning_content
          const content = data.choices?.[0]?.delta?.content
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
              const nextChunk = textBuffer.value.substring(0, 10) //长度n小于10 会截取到n
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

// 模拟流式输出（mock 模式）
function simulateMockResponse(convId: string) {
  const assistantMsg = reactive<AssistantMessage>({
    role: 'assistant',
    content: '',
    timestamp: Date.now()
  })
  messageStore.addMessage(convId, assistantMsg)
  const chunkSize = 100
  let index = 0

  mockInterval = setInterval(() => {
    if (index >= mockEventStreamText.length) {
      clearInterval(mockInterval!)
      mockInterval = null
      isGenerating.value = false
      return
    }
    const chunk = mockEventStreamText.slice(index, index + chunkSize)
    assistantMsg.content += chunk
    index += chunkSize
  }, 50)
}

function handleStop() {
  if (mockInterval) {
    clearInterval(mockInterval)
    mockInterval = null
    isGenerating.value = false
    return
  }
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
  // 新建一个会话来执行快捷问题
  if (!conversationStore.currentConversationId) {
    conversationStore.createConversation()
  }
  handleSend(question)
}

defineExpose({
  isGenerating,
  conversationStore,
  messageStore
})
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

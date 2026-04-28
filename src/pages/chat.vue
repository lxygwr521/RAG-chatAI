<template>
  <div class="chat-page flex flex-col h-screen bg-white">
    <!-- 导航标题 -->
    <NavTitle />

    <!-- 聊天主区域 -->
    <main class="chat-main flex-1 overflow-y-auto" ref="chatMainRef">
      <div class="chat-messages flex flex-col min-h-full py-4 px-5 md:px-8">
        <template v-if="messages.length !== 0">
          <template
            v-for="msg in messages"
            :key="msg.timestamp"
          >
          <UserMsg
            v-if="msg.role === 'user'"
            :message="{ content: msg.content, timestamp: msg.timestamp }"
            class="animate-message"
          />
          <AssistantMsg
            v-else
            :message="{ content: msg.content, timestamp: msg.timestamp }"
            class="animate-message"
            style="width: 100%;"
          />
          </template>
        </template>
        <template v-else>
           <NoData />
        </template>
        <!-- 底部占位，确保新消息在可视区域 -->
        <div class="h-20 shrink-0" />
      </div>
    </main>

    <!-- 快捷问题：位于输入区域上方 -->
    <QuickQuestions
      :questions="mockQuestions"
      @select="handleQuickQuestion"
    />

    <!-- 输入区域 -->
    <ChatInput
      :is-generating="isGenerating"
      @submit="handleSend"
      @stop="handleStop"
    />
    <button @click="handleTest">测试</button>
  </div>
</template>

<script setup lang="ts">
import callLLM from '@/stores/index'
import { ref, reactive, nextTick, watch } from 'vue'
import NavTitle from '@/components/NavTitle/index.vue'
import { UserMsg, AssistantMsg, ChatInput, QuickQuestions, mockQuestions } from '@/components/chat/mock'
import type { UserMessage, AssistantMessage } from '@/components/chat/types'
import NoData from '@/components/noData.vue'
import { renderMarkdownText } from '@/utils/markdown'
import { mockEventStreamText } from '@/mock'
const messages = ref<(UserMessage | AssistantMessage)[]>([])
const chatMainRef = ref<HTMLElement | null>(null)
const isGenerating = ref(false)
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

function handleTest() {
  const html = renderMarkdownText(mockEventStreamText)
  console.log(html)
  document.body.innerHTML = html
  document.body.classList.add('markdown-wrapper')
}
// 监听消息变化，自动滚动
watch(messages, () => {
  scrollToBottom()
}, { deep: true })

function handleSend(question: string) {
  // debugger
  const userMsg: UserMessage = {
    role: 'user',
    content: question,
    timestamp: Date.now(),
  }
  messages.value.push(userMsg)
  isGenerating.value = true
  currentController = new AbortController()
  callLLM(question, currentController).then(async res => {
    if(res.reader){
      currentReader = res.reader
      const reader = currentReader
      const assistantMsg = reactive<AssistantMessage>({
        role: 'assistant',
        content: '',
        timestamp: Date.now(),
      })
      messages.value.push(assistantMsg)
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        if (!value) continue
        if (value.trim() === '[DONE]') break

        const data = JSON.parse(value || '{}')
        const content = data.choices?.[0]?.delta?.content

        if (content) {
          textBuffer.value += content
          if (textBuffer.value.length > 0) {
            const nextChunk = textBuffer.value.substring(0, 10)
            assistantMsg.content += nextChunk
            textBuffer.value = textBuffer.value.substring(10)
          }

          // assistantMsg.content = markdownToHtml(rawText)
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
  if(isGenerating.value) return
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

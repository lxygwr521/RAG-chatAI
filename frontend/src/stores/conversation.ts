import { defineStore } from 'pinia'
import { ref, reactive, computed } from 'vue'
import type { Message } from '@/components/chat/types'
import { v4 as uuidv4 } from 'uuid'
import {
  fetchConversations as apiFetchConversations,
  fetchMessages as apiFetchMessages,
  deleteConversation as apiDeleteConversation,
  type BackendConversation,
  type BackendMessage,
} from '@/api/conversation'

export interface Conversation {
  id: string
  title: string
  createdAt: number
  model: string
}

// ---------------------------------------------------------------------------
// useConversationStore — 管理所有会话的元数据
// 数据来源: 后端 SQLite (GET /api/conversations)，内存中维护当前会话状态
// ---------------------------------------------------------------------------
export const useConversationStore = defineStore('conversation', () => {
  const conversations = ref<Conversation[]>([])
  const currentConversationId = ref<string | null>(null)
  const selectedModel = ref('deepseek')
  const loaded = ref(false)

  const currentConversation = computed(() =>
    conversations.value.find(c => c.id === currentConversationId.value) ?? null
  )

  // 从后端加载会话列表
  async function loadFromBackend() {
    try {
      const data = await apiFetchConversations()
      conversations.value = data.map((c: BackendConversation) => ({
        id: c.id,
        title: c.title,
        createdAt: c.created_at,
        model: c.model,
      }))
      loaded.value = true
    } catch (e) {
      console.error('加载会话列表失败:', e)
    }
  }

  function createConversation(): Conversation {
    const conv: Conversation = {
      id: uuidv4(),
      title: '新对话',
      createdAt: Date.now(),
      model: selectedModel.value,
    }
    conversations.value.unshift(conv)
    currentConversationId.value = conv.id
    return conv
  }

  async function deleteConversation(id: string) {
    // 删除后端数据
    try {
      await apiDeleteConversation(id)
    } catch (e) {
      console.error('删除会话失败:', e)
    }

    const idx = conversations.value.findIndex(c => c.id === id)
    if (idx === -1) return
    conversations.value.splice(idx, 1)

    if (currentConversationId.value === id) {
      if (conversations.value.length > 0) {
        currentConversationId.value = conversations.value[0]!.id
      } else {
        currentConversationId.value = null
      }
    }
  }

  function clearAllConversations() {
    conversations.value = []
    currentConversationId.value = null
  }

  function switchConversation(id: string) {
    currentConversationId.value = id
  }

  function updateConversationTitle(id: string, title: string) {
    const conv = conversations.value.find(c => c.id === id)
    if (conv) conv.title = title
  }

  function updateConversationModel(id: string, model: string) {
    const conv = conversations.value.find(c => c.id === id)
    if (conv) conv.model = model
  }

  return {
    conversations,
    currentConversationId,
    selectedModel,
    currentConversation,
    loaded,
    loadFromBackend,
    createConversation,
    deleteConversation,
    clearAllConversations,
    switchConversation,
    updateConversationTitle,
    updateConversationModel,
  }
})

// ---------------------------------------------------------------------------
// useMessageStore — 管理所有会话的消息列表
// 数据来源: 后端 SQLite (GET /api/conversations/:id/messages)，内存中维护
// ---------------------------------------------------------------------------
export const useMessageStore = defineStore('message', () => {
  const messageMap = reactive<Record<string, Message[]>>({})

  // 摘要状态（后端维护，前端仅做缓存）
  const summaryMap = reactive<Record<string, {
    text: string
    summarizedCount: number
  }>>({})

  // 从后端加载指定会话的消息
  async function loadMessages(conversationId: string) {
    try {
      const data = await apiFetchMessages(conversationId)
      messageMap[conversationId] = data.map((m: BackendMessage) => ({
        role: m.role as 'user' | 'assistant',
        content: m.content,
        thinkingContent: m.thinking_content ?? undefined,
        timestamp: m.timestamp,
        citations: m.citations_json ? JSON.parse(m.citations_json) : undefined,
        files: m.files_json ? JSON.parse(m.files_json) : undefined,
      }))
    } catch (e) {
      console.error('加载消息失败:', e)
    }
  }

  // conversation store 调用 switchConversation 后，加载消息
  // 外部通过 messageStore.loadMessages(id) 触发

  function getSummary(conversationId: string) {
    return summaryMap[conversationId] ?? null
  }

  function setSummary(conversationId: string, text: string, summarizedCount: number) {
    summaryMap[conversationId] = { text, summarizedCount }
  }

  function clearSummary(conversationId: string) {
    delete summaryMap[conversationId]
  }

  function getMessages(conversationId: string): Message[] {
    return messageMap[conversationId] ?? []
  }

  function addMessage(conversationId: string, msg: Message) {
    if (!messageMap[conversationId]) {
      messageMap[conversationId] = []
    }
    messageMap[conversationId].push(msg)
  }

  function updateLastMessage(conversationId: string, update: Partial<Message>) {
    const messages = messageMap[conversationId]
    if (!messages || messages.length === 0) return
    const last = messages[messages.length - 1]
    if (last && last.role === 'assistant') {
      Object.assign(last, update)
    }
  }

  function deleteConversationMessages(conversationId: string) {
    delete messageMap[conversationId]
    delete summaryMap[conversationId]
  }

  function clearAllMessages() {
    Object.keys(messageMap).forEach(key => delete messageMap[key])
    Object.keys(summaryMap).forEach(key => delete summaryMap[key])
  }

  return {
    messageMap,
    summaryMap,
    getMessages,
    addMessage,
    updateLastMessage,
    loadMessages,
    getSummary,
    setSummary,
    clearSummary,
    deleteConversationMessages,
    clearAllMessages,
  }
})

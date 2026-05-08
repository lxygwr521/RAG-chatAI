import { defineStore } from 'pinia'
import { ref, reactive, computed } from 'vue'
import type { UserMessage, AssistantMessage } from '@/components/chat/types'
import { v4 as uuidv4 } from 'uuid'

export interface Conversation {
  id: string
  title: string
  createdAt: number
  model: string
}

// ---------------------------------------------------------------------------
// useConversationStore — 管理所有会话的元数据
// ---------------------------------------------------------------------------
export const useConversationStore = defineStore('conversation', () => {
  const conversations = ref<Conversation[]>([])
  const currentConversationId = ref<string | null>(null)
  const selectedModel = ref('mock')

  // 当前激活的会话对象
  const currentConversation = computed(() =>
    conversations.value.find(c => c.id === currentConversationId.value) ?? null
  )

  function createConversation(): Conversation {
    const conv: Conversation = {
      id: uuidv4(),
      title: '新对话',
      createdAt: Date.now(),
      model: selectedModel.value
    }
    conversations.value.unshift(conv)
    currentConversationId.value = conv.id
    return conv
  }

  function deleteConversation(id: string) {
    const idx = conversations.value.findIndex(c => c.id === id)
    if (idx === -1) return
    conversations.value.splice(idx, 1)

    // 如果删除的是当前会话，切换到第一个会话或新建
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
    createConversation,
    deleteConversation,
    clearAllConversations,
    switchConversation,
    updateConversationTitle,
    updateConversationModel
  }
}, {
  persist: {
    key: 'chat-conversations',
    storage: localStorage
  }
})

// ---------------------------------------------------------------------------
// useMessageStore — 管理所有会话的消息列表
// ---------------------------------------------------------------------------
export const useMessageStore = defineStore('message', () => {
  // reactive 保证嵌套对象变更触发响应式更新
  const messageMap = reactive<Record<string, (UserMessage | AssistantMessage)[]>>({})

  function getMessages(conversationId: string): (UserMessage | AssistantMessage)[] {
    return messageMap[conversationId] ?? []
  }

  function addMessage(conversationId: string, msg: UserMessage | AssistantMessage) {
    if (!messageMap[conversationId]) {
      messageMap[conversationId] = []
    }
    messageMap[conversationId].push(msg)
  }

  function updateLastMessage(conversationId: string, update: Partial<AssistantMessage>) {
    const messages = messageMap[conversationId]
    if (!messages || messages.length === 0) return
    const last = messages[messages.length - 1]
    if (last && last.role === 'assistant') {
      Object.assign(last, update)
    }
  }

  function deleteConversationMessages(conversationId: string) {
    delete messageMap[conversationId]
  }

  function clearAllMessages() {
    Object.keys(messageMap).forEach(key => delete messageMap[key])
  }

  return {
    messageMap,
    getMessages,
    addMessage,
    updateLastMessage,
    deleteConversationMessages,
    clearAllMessages
  }
}, {
  persist: {
    key: 'chat-messages',
    storage: localStorage
  }
})

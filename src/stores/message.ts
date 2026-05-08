import { defineStore } from 'pinia'
import type { Message } from '@/components/chat/types'

export const useMessageStore = defineStore('message', () => {
  const messageMap = ref<Record<string, Message[]>>({})

  function getMessages(conversationId: string): Message[] {
    return messageMap.value[conversationId] ?? []
  }

  function addMessage(conversationId: string, msg: Message) {
    if (!messageMap.value[conversationId]) {
      messageMap.value[conversationId] = []
    }
    messageMap.value[conversationId].push(msg)
  }

  function updateLastMessage(conversationId: string, content: string) {
    const msgs = messageMap.value[conversationId]
    if (!msgs || msgs.length === 0) return
    const last = msgs[msgs.length - 1]
    if (last.role === 'assistant') {
      last.content = content
    }
  }

  function deleteMessages(conversationId: string) {
    delete messageMap.value[conversationId]
  }

  function clearAllMessages() {
    messageMap.value = {}
  }

  return {
    messageMap,
    getMessages,
    addMessage,
    updateLastMessage,
    deleteMessages,
    clearAllMessages,
  }
}, {
  persist: true,
})

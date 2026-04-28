export interface UserMessage {
  role: 'user'
  content: string
  timestamp: number
}

export interface AssistantMessage {
  role: 'assistant'
  content: string
  timestamp: number
  isTyping?: boolean
}

// Props passed to components — no role needed, component already knows its role
export interface UserMessageProps {
  content: string
  timestamp: number
}

export interface AssistantMessageProps {
  content: string
  timestamp: number
  isTyping?: boolean
}

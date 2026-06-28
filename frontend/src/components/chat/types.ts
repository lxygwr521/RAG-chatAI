export interface Conversation {
  id: string
  title: string
  createdAt: number
  model: string
}

export type Message = UserMessage | AssistantMessage

export interface UserMessage {
  role: 'user'
  content: string
  timestamp: number
  files?: UploadFile[]
}

export interface AssistantMessage {
  role: 'assistant'
  content: string
  thinkingContent?: string
  citations?: Citation[]
  timestamp: number
  isTyping?: boolean
}

export interface Citation {
  document: string
  snippet: string
  score: number
  chunk_id: string
}

// Props passed to components — no role needed, component already knows its role

export interface AssistantMessageProps {
  content: string
  thinkingContent?: string
  citations?: Citation[]
  timestamp: number
  isTyping?: boolean
}

export interface UserMessageProps {
  content: string
  timestamp: number
  files?: UploadFile[]
}

export interface UploadFile {
  id: string
  file: File
  url?: string
}

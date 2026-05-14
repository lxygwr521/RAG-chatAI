import * as TransformUtils from '@/utils/transform'
import type { UploadFile } from '@/components/chat/types'
import { useConversationStore } from '../stores/conversation'
interface LLMMessage {
  role: string
  content: string
}

type ThinkingType = 'enabled' | 'disabled'
type ReasoningEffort = 'low' | 'medium' | 'high'

interface Payload {
  model: string
  messages: LLMMessage[]
  stream?: boolean
  thinking?: {
    type: ThinkingType
  }
  reasoning_effort?: ReasoningEffort
}

const url = 'https://api.deepseek.com/chat/completions'
const headers = {
  'Content-Type': 'application/json',
  Authorization: `Bearer ${import.meta.env.VITE_DEEPSEEK_API_KEY}`
}
// 文件内容读取
async function readFiles(files: UploadFile[]): Promise<string> {
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

// 构建用户消息内容（含附件）
async function buildUserContent(
  question: string,
  files: UploadFile[]
): Promise<string> {
  if (!files || files.length === 0) return question
  const fileContent = await readFiles(files)
  return `${fileContent}\n\n---\n\n${question}`.trim()
}

// 发起 fetch 请求
// messages 包含完整的对话历史（system + 交替的 user/assistant）
async function callLLM(
  messages: LLMMessage[],
  controller?: AbortController
): Promise<{ error: number; reader: ReadableStreamDefaultReader<string> | null }> {
  const conversationStore = useConversationStore()
  const isThinkModel: ThinkingType = conversationStore.selectedModel === 'deepseek-think' ? 'enabled' : 'disabled'

  const payload: Payload = {
    model: 'deepseek-v4-flash',
    thinking: { "type": isThinkModel },
    stream: true,
    messages
  }

  if (isThinkModel === 'enabled') {
    payload.reasoning_effort = 'high'
  }

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
      signal: controller?.signal
    })
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    if (response.body) {
      const reader = response.body
        .pipeThrough(new TextDecoderStream())
        .pipeThrough(TransformUtils.splitStream('\n'))
        .getReader()
      return { error: 0, reader: reader as ReadableStreamDefaultReader<string> }
    } else {
      return { error: 1, reader: null }
    }
  } catch {
    return { error: 1, reader: null }
  }
}

export { buildUserContent, readFiles, type LLMMessage }
export default callLLM

import { estimateTokens } from './token'
import type { LLMMessage } from '@/api/llm'

const MAX_CONTEXT_TOKENS = 80000
const RECENT_WINDOW_SIZE = 20

const API_URL = 'https://api.deepseek.com/chat/completions'
const API_HEADERS = {
  'Content-Type': 'application/json',
  Authorization: `Bearer ${import.meta.env.VITE_DEEPSEEK_API_KEY}`
}

export interface ContextParams {
  systemPrompt: string
  history: LLMMessage[]
  userContent: string
  existingSummary?: string
  summarizedCount?: number
}

export interface BuildContextResult {
  messages: LLMMessage[]
  newSummary?: {
    text: string
    coveredCount: number
  }
}

function formatMessagesForSummary(msgs: LLMMessage[]): string {
  return msgs
    .map(m => `${m.role === 'user' ? '用户' : '助手'}: ${m.content}`)
    .join('\n\n')
}

async function generateSummary(
  existingSummary: string | undefined,
  newMessages: LLMMessage[]
): Promise<string> {
  const conversationText = formatMessagesForSummary(newMessages)
  const prompt = existingSummary
    ? `之前的对话摘要：\n${existingSummary}\n\n新的对话内容：\n${conversationText}\n\n请将以上内容合并为一个完整的对话摘要（200字以内），保留关键事实、用户偏好、重要决策和待办事项。只输出摘要文本。`
    : `请将以下对话内容压缩为简洁的摘要（200字以内），保留所有关键事实、用户偏好、重要决策和待办事项。只输出摘要文本。\n\n${conversationText}`

  const response = await fetch(API_URL, {
    method: 'POST',
    headers: API_HEADERS,
    body: JSON.stringify({
      model: 'deepseek-v4-flash',
      messages: [
        { role: 'system', content: '你是一个对话摘要助手，只输出简洁的摘要。' },
        { role: 'user', content: prompt }
      ],
      stream: false,
      max_tokens: 400  //设置max_token来控制输出的摘要内容是精简的
    })
  })

  if (!response.ok) {
    throw new Error(`摘要请求失败: ${response.status}`)
  }

  const data = await response.json() as {
    choices: Array<{ message: { content: string } }>
  }
  return data.choices[0]!.message.content
}

export async function buildContext(params: ContextParams): Promise<BuildContextResult> {
  const { systemPrompt, history, userContent, existingSummary, summarizedCount = 0 } = params

  // 未摘要覆盖的消息（summarizedCount 之前的消息已压缩为摘要，不再重复计入）
  const unsummarizedHistory = history.slice(summarizedCount)
  const historyTokens = unsummarizedHistory.reduce((sum, m) => sum + estimateTokens(m.content), 0)
  const systemTokens = estimateTokens(systemPrompt)
  const summaryTokens = existingSummary ? estimateTokens(existingSummary) : 0
  const userTokens = estimateTokens(userContent)
  const totalTokens = systemTokens + summaryTokens + historyTokens + userTokens

  // 未超阈值：返回完整上下文
  if (totalTokens <= MAX_CONTEXT_TOKENS) {
    const messages: LLMMessage[] = [
      { role: 'system', content: systemPrompt }
    ]
    if (existingSummary) {
      messages.push({
        role: 'system',
        content: `[历史对话摘要]\n${existingSummary}`
      })
    }
    messages.push(...unsummarizedHistory)
    messages.push({ role: 'user', content: userContent })
    return { messages }
  }

  // 超阈值：从未摘要的消息中分离早期 / 近期
  // unsummarizedHistory:  [A, B, C, D, E, F, G, H, I, J]   (10条，假设窗口=3)
  //     slice(-3)    =                [H, I, J]  ← recentMessages   保留原文不动                         │
  //     slice(0, -3) = [A, B, C, D, E, F, G]  ← newEarlyMessages  送去摘要压缩

  const recentMessages = unsummarizedHistory.slice(-RECENT_WINDOW_SIZE) //需要保留完整原文的
  const newEarlyMessages = unsummarizedHistory.slice(0, -RECENT_WINDOW_SIZE)

  // 如果没有新的早期消息需要摘要，直接滑窗返回
  if (newEarlyMessages.length === 0) {
    const messages: LLMMessage[] = [
      { role: 'system', content: systemPrompt }
    ]
    if (existingSummary) {
      messages.push({
        role: 'system',
        content: `[历史对话摘要]\n${existingSummary}`
      })
    }
    messages.push(...recentMessages)
    messages.push({ role: 'user', content: userContent })
    return { messages }
  }

  // 调用摘要 API
  try {
    const newSummaryText = await generateSummary(existingSummary, newEarlyMessages)
    const newCoveredCount = summarizedCount + newEarlyMessages.length

    return {
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'system', content: `[历史对话摘要]\n${newSummaryText}` },
        ...recentMessages,
        { role: 'user', content: userContent }
      ],
      newSummary: {
        text: newSummaryText,
        coveredCount: newCoveredCount
      }
    }
  } catch {
    // 降级：摘要失败时使用滑窗截断
    console.warn('摘要生成失败，降级为滑窗截断')
    const messages: LLMMessage[] = [
      { role: 'system', content: systemPrompt }
    ]
    if (existingSummary) {
      messages.push({
        role: 'system',
        content: `[历史对话摘要]\n${existingSummary}`
      })
    }
    messages.push(...recentMessages)
    messages.push({ role: 'user', content: userContent })
    return { messages }
  }
}

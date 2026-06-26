/**
 * 估算文本的 token 数量。
 * 使用字符比例估算：中文约 1.5 字符/token，英文约 4 字符/token，
 * 取保守值 Math.ceil(len / 2.5) 以保护上下文窗口不超限。
 */
export function estimateTokens(text: string): number {
  if (!text) return 0
  return Math.ceil(text.length / 2.5)
}

export function estimateTokensBatch(texts: string[]): number {
  return texts.reduce((sum, t) => sum + estimateTokens(t), 0)
}

/** Backend conversation CRUD client. */

export interface BackendConversation {
  id: string
  title: string
  model: string
  created_at: number
  updated_at: number
  message_count: number
}

export interface BackendMessage {
  id: number
  role: string
  content: string
  thinking_content: string | null
  files_json: string | null
  citations_json: string | null
  timestamp: number
}

export async function fetchConversations(): Promise<BackendConversation[]> {
  const resp = await fetch('/api/conversations')
  if (!resp.ok) throw new Error(`Fetch conversations failed: ${resp.status}`)
  return resp.json()
}

export async function createConversation(
  title: string,
  model: string
): Promise<BackendConversation> {
  const resp = await fetch('/api/conversations', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, model }),
  })
  if (!resp.ok) throw new Error(`Create conversation failed: ${resp.status}`)
  return resp.json()
}

export async function deleteConversation(id: string): Promise<void> {
  const resp = await fetch(`/api/conversations/${id}`, { method: 'DELETE' })
  if (!resp.ok) throw new Error(`Delete conversation failed: ${resp.status}`)
}

export async function fetchMessages(
  convId: string,
  offset = 0,
  limit = 100
): Promise<BackendMessage[]> {
  const resp = await fetch(
    `/api/conversations/${convId}/messages?offset=${offset}&limit=${limit}`
  )
  if (!resp.ok) throw new Error(`Fetch messages failed: ${resp.status}`)
  return resp.json()
}

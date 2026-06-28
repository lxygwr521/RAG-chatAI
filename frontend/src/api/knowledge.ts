/** Backend knowledge base CRUD client. */

export interface DocumentInfo {
  id: string
  filename: string
  file_type: string
  file_size: number
  chunk_count: number
  status: string
  created_at: number
}

export async function uploadDocuments(files: File[]): Promise<DocumentInfo[]> {
  const formData = new FormData()
  files.forEach(f => formData.append('files', f))

  const resp = await fetch('/api/knowledge/documents', {
    method: 'POST',
    body: formData,
  })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: 'Upload failed' }))
    throw new Error(err.detail || `Upload failed: ${resp.status}`)
  }
  return resp.json()
}

export async function fetchDocuments(): Promise<DocumentInfo[]> {
  const resp = await fetch('/api/knowledge/documents')
  if (!resp.ok) throw new Error(`Fetch documents failed: ${resp.status}`)
  return resp.json()
}

export async function deleteDocument(id: string): Promise<void> {
  const resp = await fetch(`/api/knowledge/documents/${id}`, { method: 'DELETE' })
  if (!resp.ok) throw new Error(`Delete document failed: ${resp.status}`)
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

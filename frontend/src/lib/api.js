// Single place that talks to the backend. Relative /api URLs work both in dev
// (Vite proxies /api -> :8000) and in production (FastAPI serves dist + /api on
// the same origin), so there's no hardcoded host and no CORS dependency.

async function json(res) {
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

export function newSessionId() {
  return (crypto?.randomUUID && crypto.randomUUID()) || String(Math.random()).slice(2)
}

export async function uploadFiles(fileList) {
  const fd = new FormData()
  Array.from(fileList).forEach((f) => fd.append('files', f))
  return json(await fetch('/api/upload', { method: 'POST', body: fd }))
}

export async function getStatus(docId) {
  return json(await fetch(`/api/status/${docId}`))
}

export async function sendChat(sessionId, message) {
  return json(
    await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, message }),
    }),
  )
}

export async function getChunks() {
  return json(await fetch('/api/chunks'))
}

export async function listConversations(q) {
  const url = q ? `/api/conversations?q=${encodeURIComponent(q)}` : '/api/conversations'
  return json(await fetch(url))
}

export async function getConversation(id) {
  return json(await fetch(`/api/conversations/${encodeURIComponent(id)}`))
}

export async function deleteConversation(id) {
  return json(await fetch(`/api/conversations/${encodeURIComponent(id)}`, { method: 'DELETE' }))
}

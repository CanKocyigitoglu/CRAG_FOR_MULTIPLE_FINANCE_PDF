import { useEffect, useRef, useState } from 'react'
import ConversationSidebar from '../components/ConversationSidebar.jsx'
import UploadPanel from '../components/UploadPanel.jsx'
import MessageBubble from '../components/MessageBubble.jsx'
import { sendChat, uploadFiles, getStatus, getConversation } from '../lib/api.js'
import './ChatView.css'

// Server history (role: 'user' | 'assistant') -> UI bubbles (role: 'user' | 'bot').
function toUiMessages(serverMessages) {
  return serverMessages.map((m) =>
    m.role === 'user'
      ? { role: 'user', text: m.content }
      : { role: 'bot', text: m.content, citations: m.citations || [] },
  )
}

export default function ChatView({ sessionId, onSelectSession, onNewChat }) {
  const [docs, setDocs] = useState([])
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [version, setVersion] = useState(0) // bump to refresh the sidebar list
  const logRef = useRef(null)

  // Load this conversation's history whenever the session changes: initial mount
  // (restored from localStorage), sidebar select, or new chat. A 404 = a brand
  // new / empty conversation, so we clear the log.
  useEffect(() => {
    let alive = true
    getConversation(sessionId)
      .then((conv) => alive && setMessages(toUiMessages(conv.messages)))
      .catch(() => alive && setMessages([]))
    return () => {
      alive = false
    }
  }, [sessionId])

  useEffect(() => {
    logRef.current?.scrollTo(0, logRef.current.scrollHeight)
  }, [messages])

  function patchDoc(docId, patch) {
    setDocs((ds) => ds.map((d) => (d.doc_id === docId ? { ...d, ...patch } : d)))
  }

  async function pollStatus(docId) {
    for (let i = 0; i < 600; i++) {
      try {
        const s = await getStatus(docId)
        patchDoc(docId, { status: s.status, chunks: s.chunks })
        if (s.status !== 'indexing') return
      } catch {
        /* transient */
      }
      await new Promise((r) => setTimeout(r, 1500))
    }
  }

  async function handleFiles(files) {
    if (!files?.length) return
    try {
      const started = await uploadFiles(files)
      setDocs((ds) => [...ds, ...started])
      started.forEach((d) => pollStatus(d.doc_id))
    } catch {
      alert('Upload failed — is the API running on :8000?')
    }
  }

  async function handleSend(e) {
    e.preventDefault()
    const q = input.trim()
    if (!q || sending) return
    setInput('')
    setSending(true)
    setMessages((m) => [...m, { role: 'user', text: q }, { role: 'bot', pending: true }])
    try {
      const res = await sendChat(sessionId, q)
      setMessages((m) => {
        const next = m.slice(0, -1)
        return [...next, { role: 'bot', text: res.answer, citations: res.citations || [] }]
      })
      setVersion((v) => v + 1) // new conversation / retitle / reorder -> refresh sidebar
    } catch {
      setMessages((m) => {
        const next = m.slice(0, -1)
        return [...next, { role: 'bot', text: 'Request failed — is the API running?', error: true }]
      })
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="chat-view">
      <ConversationSidebar
        currentId={sessionId}
        version={version}
        onSelect={onSelectSession}
        onNew={onNewChat}
        onDeletedCurrent={onNewChat}
      />
      <UploadPanel docs={docs} onFiles={handleFiles} />

      <section className="chat-main">
        <div className="chat-log" ref={logRef}>
          {messages.length === 0 ? (
            <div className="chat-empty">
              Ask a question about your indexed documents.
              <br />A demo file (<span className="mono">sample_financials.pdf</span>) is already indexed.
            </div>
          ) : (
            messages.map((m, i) => <MessageBubble key={i} msg={m} />)
          )}
        </div>

        <form className="chat-input" onSubmit={handleSend}>
          <input
            type="text"
            placeholder="Ask about the documents…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            autoFocus
          />
          <button type="submit" disabled={sending || !input.trim()}>
            {sending ? '…' : 'Send'}
          </button>
        </form>
      </section>
    </div>
  )
}

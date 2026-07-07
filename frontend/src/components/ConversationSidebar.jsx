import { useEffect, useState } from 'react'
import { listConversations, deleteConversation } from '../lib/api.js'
import './ConversationSidebar.css'

// Past-conversation rail: list + search + delete + "new chat". Re-fetches when
// the search term changes or `version` bumps (parent bumps it after each send,
// so a new conversation / retitle / reorder shows up).
export default function ConversationSidebar({ currentId, version, onSelect, onNew, onDeletedCurrent }) {
  const [items, setItems] = useState([])
  const [q, setQ] = useState('')

  useEffect(() => {
    let alive = true
    listConversations(q)
      .then((rows) => alive && setItems(rows))
      .catch(() => {})
    return () => {
      alive = false
    }
  }, [q, version])

  async function handleDelete(e, id) {
    e.stopPropagation()
    try {
      await deleteConversation(id)
    } catch {
      /* already gone */
    }
    setItems((xs) => xs.filter((x) => x.id !== id))
    if (id === currentId) onDeletedCurrent()
  }

  return (
    <aside className="conv-sidebar">
      <button className="conv-new" onClick={onNew}>
        ＋ New chat
      </button>
      <input
        className="conv-search"
        placeholder="Search chats…"
        value={q}
        onChange={(e) => setQ(e.target.value)}
      />
      <div className="conv-list">
        {items.length === 0 ? (
          <div className="conv-empty">{q ? 'No matches.' : 'No conversations yet.'}</div>
        ) : (
          items.map((it) => (
            <div
              key={it.id}
              className={'conv-row' + (it.id === currentId ? ' active' : '')}
              onClick={() => onSelect(it.id)}
              title={it.title}
            >
              <span className="conv-title">{it.title || 'Untitled'}</span>
              <button className="conv-del" title="Delete" onClick={(e) => handleDelete(e, it.id)}>
                ×
              </button>
            </div>
          ))
        )}
      </div>
    </aside>
  )
}

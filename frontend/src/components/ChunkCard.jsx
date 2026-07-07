import { useState } from 'react'
import './ChunkCard.css'

// Wrap case-insensitive matches of `q` in <mark> without dangerouslySetInnerHTML.
function highlight(text, q) {
  if (!q) return text
  const hay = text.toLowerCase()
  const needle = q.toLowerCase()
  const out = []
  let from = 0
  let i
  while ((i = hay.indexOf(needle, from)) !== -1) {
    if (i > from) out.push(text.slice(from, i))
    out.push(<mark key={i}>{text.slice(i, i + needle.length)}</mark>)
    from = i + needle.length
  }
  out.push(text.slice(from))
  return out
}

export default function ChunkCard({ chunk, query }) {
  const [open, setOpen] = useState(false)
  const sameAsChild = chunk.parent_text === chunk.text

  return (
    <article className="chunk-card">
      <header className="chunk-head">
        <span className="chunk-index badge accent">#{chunk.doc_index}</span>
        {/* provenance / citation */}
        <span className="chunk-source">
          <span className="chunk-doc">📄 {chunk.doc}</span>
          <span className="chunk-id mono">{chunk.doc_id}</span>
        </span>
        <span className="badge chunk-page">page {chunk.page}</span>
      </header>

      <div className="chunk-section">
        <div className="chunk-tag child">CHILD · indexed for retrieval</div>
        <p className="chunk-text">{highlight(chunk.text, query)}</p>
      </div>

      <div className="chunk-section">
        {sameAsChild ? (
          <div className="chunk-parent-note">
            PARENT context = same text (page fits in one chunk)
          </div>
        ) : (
          <>
            <button className="chunk-toggle" onClick={() => setOpen((o) => !o)}>
              <span className="chunk-tag parent">PARENT · sent to the LLM</span>
              <span className="chunk-caret">{open ? '▾ hide' : '▸ show'}</span>
            </button>
            {open && <p className="chunk-text parent">{highlight(chunk.parent_text, query)}</p>}
          </>
        )}
      </div>

      <footer className="chunk-foot">
        <span className="badge">child {chunk.child_len} chars</span>
        <span className="badge">parent {chunk.parent_len} chars</span>
      </footer>
    </article>
  )
}

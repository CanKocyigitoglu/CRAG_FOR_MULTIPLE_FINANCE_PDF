import { useEffect, useMemo, useState } from 'react'
import MetaBar from '../components/MetaBar.jsx'
import DocList from '../components/DocList.jsx'
import ChunkCard from '../components/ChunkCard.jsx'
import { getChunks } from '../lib/api.js'
import './ChunksView.css'

export default function ChunksView() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedDoc, setSelectedDoc] = useState(null) // doc_id | null (all)
  const [query, setQuery] = useState('')

  async function load() {
    setLoading(true)
    setError(null)
    try {
      setData(await getChunks())
    } catch (e) {
      setError(String(e.message || e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const filtered = useMemo(() => {
    if (!data) return []
    const q = query.trim().toLowerCase()
    return data.chunks.filter((c) => {
      if (selectedDoc && c.doc_id !== selectedDoc) return false
      if (q && !(c.text + ' ' + c.parent_text).toLowerCase().includes(q)) return false
      return true
    })
  }, [data, selectedDoc, query])

  return (
    <div className="chunks-view">
      <div className="chunks-header">
        <MetaBar meta={data?.meta} loading={loading} />
        <button className="refresh" onClick={load} disabled={loading}>
          ↻ Refresh
        </button>
      </div>

      <div className="chunks-body">
        <DocList
          documents={data?.documents || []}
          total={data?.meta?.total_chunks || 0}
          selected={selectedDoc}
          onSelect={setSelectedDoc}
        />

        <section className="chunks-main">
          <div className="chunks-toolbar">
            <input
              className="chunk-search"
              placeholder="Search chunk text…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <span className="chunks-count">
              {filtered.length} chunk{filtered.length === 1 ? '' : 's'}
              {selectedDoc || query ? ' (filtered)' : ''}
            </span>
          </div>

          <div className="legend">
            <span><b className="tag-child">CHILD</b> = the unit embedded &amp; BM25-indexed for retrieval</span>
            <span><b className="tag-parent">PARENT</b> = the larger context block sent to the LLM</span>
            <span>Each card shows its source document &amp; page — that's the citation.</span>
          </div>

          {loading && <div className="chunks-state">Loading chunks…</div>}
          {error && <div className="chunks-state error">Failed to load: {error}</div>}
          {!loading && !error && filtered.length === 0 && (
            <div className="chunks-state">No chunks match. Upload a PDF in Chat, or clear the filter.</div>
          )}

          <div className="chunk-grid">
            {filtered.map((c, i) => (
              <ChunkCard key={`${c.doc_id}-${c.page}-${i}`} chunk={c} query={query} />
            ))}
          </div>
        </section>
      </div>
    </div>
  )
}

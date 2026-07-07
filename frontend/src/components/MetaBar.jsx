import './MetaBar.css'

// "Where / how the data is stored" — index-level metadata for the corpus.
function Stat({ label, value, accent }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className={'stat-value' + (accent ? ' accent' : '')}>{value ?? '—'}</div>
    </div>
  )
}

export default function MetaBar({ meta, loading }) {
  const m = meta || {}
  return (
    <div className="metabar" title="Index-level metadata: where and how these chunks are stored">
      <Stat label="Vector store" value="Qdrant" accent />
      <Stat label="Collection" value={loading ? '…' : m.collection} />
      <Stat label="Embedding model" value={loading ? '…' : m.embedding_model} />
      <Stat label="Vector dim" value={loading ? '…' : m.vector_dim} />
      <Stat label="Distance" value={loading ? '…' : m.distance} />
      <Stat label="Documents" value={loading ? '…' : m.total_documents} accent />
      <Stat label="Chunks" value={loading ? '…' : m.total_chunks} accent />
    </div>
  )
}

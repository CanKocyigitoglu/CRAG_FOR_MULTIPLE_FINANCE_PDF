import './DocList.css'

// Filter the chunk grid by source document. "All documents" clears the filter.
export default function DocList({ documents, total, selected, onSelect }) {
  return (
    <aside className="doclist">
      <div className="doclist-title">Documents</div>

      <button
        className={'doc-item' + (selected === null ? ' active' : '')}
        onClick={() => onSelect(null)}
      >
        <span className="doc-item-name">All documents</span>
        <span className="badge">{total}</span>
      </button>

      {documents.map((d) => (
        <button
          key={d.doc_id}
          className={'doc-item' + (selected === d.doc_id ? ' active' : '')}
          onClick={() => onSelect(d.doc_id)}
          title={`doc_id: ${d.doc_id}`}
        >
          <span className="doc-item-body">
            <span className="doc-item-name">📄 {d.doc}</span>
            <span className="doc-item-id mono">{d.doc_id}</span>
          </span>
          <span className="badge">{d.chunks}</span>
        </button>
      ))}

      {documents.length === 0 && <div className="doclist-empty">No documents indexed yet.</div>}
    </aside>
  )
}

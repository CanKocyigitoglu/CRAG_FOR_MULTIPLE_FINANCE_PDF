import { useRef } from 'react'
import './UploadPanel.css'

function StatusBadge({ status, chunks }) {
  const cls = status === 'ready' ? 'ready' : status === 'error' ? 'error' : 'indexing'
  const label = status === 'ready' ? `ready · ${chunks} chunks` : status
  return <span className={'doc-status ' + cls}>{label}</span>
}

export default function UploadPanel({ docs, onFiles }) {
  const inputRef = useRef(null)

  return (
    <aside className="upload-panel">
      <label
        className="dropzone"
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault()
          onFiles(e.dataTransfer.files)
        }}
      >
        <span className="dz-plus">＋</span>
        Upload PDF(s) to index
        <span className="dz-hint">click or drop files</span>
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf"
          multiple
          hidden
          onChange={(e) => {
            onFiles(e.target.files)
            e.target.value = ''
          }}
        />
      </label>

      <div className="doc-list">
        {docs.length === 0 ? (
          <div className="doc-empty">No uploads this session.</div>
        ) : (
          docs.map((d) => (
            <div className="doc-row" key={d.doc_id} title={d.filename}>
              <span className="doc-name">{d.filename}</span>
              <StatusBadge status={d.status} chunks={d.chunks} />
            </div>
          ))
        )}
      </div>
    </aside>
  )
}

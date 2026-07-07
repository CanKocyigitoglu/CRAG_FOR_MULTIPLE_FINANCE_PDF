import './TopBar.css'

const TABS = [
  { key: 'chat', label: 'Chat', icon: '💬' },
  { key: 'chunks', label: 'Chunks Explorer', icon: '🧩' },
]

export default function TopBar({ view, onChange }) {
  return (
    <header className="topbar">
      <div className="brand">
        <span className="brand-mark">◆</span>
        <div>
          <div className="brand-name">Finance RAG</div>
          <div className="brand-sub">Grounded, cited answers over finance PDFs</div>
        </div>
      </div>
      <nav className="tabs">
        {TABS.map((t) => (
          <button
            key={t.key}
            className={'tab' + (view === t.key ? ' active' : '')}
            onClick={() => onChange(t.key)}
          >
            <span aria-hidden>{t.icon}</span>
            {t.label}
          </button>
        ))}
      </nav>
    </header>
  )
}

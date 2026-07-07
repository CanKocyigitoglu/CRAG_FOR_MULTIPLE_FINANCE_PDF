import CitationCard from './CitationCard.jsx'
import './MessageBubble.css'

export default function MessageBubble({ msg }) {
  if (msg.role === 'user') {
    return <div className="bubble user">{msg.text}</div>
  }

  return (
    <div className="bubble bot">
      {msg.pending ? (
        <span className="typing">thinking…</span>
      ) : (
        <>
          <div className={'answer' + (msg.error ? ' error' : '')}>{msg.text}</div>
          {msg.citations?.length > 0 && (
            <div className="citations">
              <div className="citations-label">Sources</div>
              {msg.citations.map((c, i) => (
                <CitationCard key={i} n={i + 1} c={c} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}

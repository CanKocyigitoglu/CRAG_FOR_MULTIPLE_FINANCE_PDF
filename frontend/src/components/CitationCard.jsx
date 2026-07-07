import './CitationCard.css'

// One source reference under a chat answer. Provenance = doc + page; the snippet
// is the retrieved chunk text the answer was grounded on.
export default function CitationCard({ n, c }) {
  return (
    <div className="citation">
      <div className="citation-head">
        <span className="citation-n">[{n}]</span>
        <span className="citation-doc">📄 {c.doc}</span>
        {c.page != null && <span className="badge">p.{c.page}</span>}
        {c.match != null && (
          <span className="badge accent citation-match" title="Semantic match of this source to your question">
            {c.match}% match
          </span>
        )}
      </div>
      {c.snippet && <div className="citation-snippet">{c.snippet}</div>}
    </div>
  )
}

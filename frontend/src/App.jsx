import { useEffect, useState } from 'react'
import TopBar from './components/TopBar.jsx'
import ChatView from './views/ChatView.jsx'
import ChunksView from './views/ChunksView.jsx'
import { newSessionId } from './lib/api.js'
import './styles/app.css'

export default function App() {
  const [view, setView] = useState('chat')
  // Persist the session id so a reload continues the same conversation instead
  // of orphaning it. "New chat" mints a fresh id; the sidebar selects existing ones.
  const [sessionId, setSessionId] = useState(
    () => localStorage.getItem('sessionId') || newSessionId(),
  )

  useEffect(() => {
    localStorage.setItem('sessionId', sessionId)
  }, [sessionId])

  return (
    <div className="app">
      <TopBar view={view} onChange={setView} />
      <main className="app-body">
        {view === 'chat' ? (
          <ChatView
            sessionId={sessionId}
            onSelectSession={setSessionId}
            onNewChat={() => setSessionId(newSessionId())}
          />
        ) : (
          <ChunksView />
        )}
      </main>
    </div>
  )
}

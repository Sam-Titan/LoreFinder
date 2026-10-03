import { useState, useRef, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { queryDocument, getHistory } from '../api/lorefinder'
import LoadingSpinner from '../components/LoadingSpinner'

function CitationPill({ citation }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '4px',
      padding: '3px 10px', marginRight: '6px', marginTop: '6px',
      borderRadius: '20px', fontSize: '12px', fontWeight: 500,
      background: 'var(--sky-dim)', color: 'var(--sky)',
      border: '1px solid rgba(78,168,222,0.2)'
    }}>
      {citation.chapter_title
        ? `${citation.chapter_title} · Chunk ${citation.chunk_index}`
        : `Ch. ${citation.chapter_number} · Chunk ${citation.chunk_index}`
      }
    </span>
  )
}

// Renders the handful of markdown patterns the model actually produces
// (bold, bullet lists) as real elements instead of literal ** and - marks.
// Deliberately not a general markdown renderer and never uses
// dangerouslySetInnerHTML — every text fragment still goes through React's
// normal escaping, so this can't become an XSS vector for LLM-generated text.
function renderInline(line, keyPrefix) {
  return line.split(/(\*\*[^*]+\*\*)/g).map((part, i) => {
    if (part.length > 4 && part.startsWith('**') && part.endsWith('**')) {
      return <strong key={`${keyPrefix}-${i}`}>{part.slice(2, -2)}</strong>
    }
    return part ? <span key={`${keyPrefix}-${i}`}>{part}</span> : null
  })
}

// Groups consecutive bullet lines into a <ul>, and consecutive non-bullet
// lines into a <p> — rather than requiring an entire double-newline block to
// be uniformly one or the other, since the model often runs a lead-in
// sentence straight into a bullet list with only a single newline between
// them (no blank-line separator).
function renderFormattedText(text) {
  const blocks = text.trim().split(/\n{2,}/)
  const elements = []
  let key = 0

  for (const block of blocks) {
    const lines = block.split('\n').map(l => l.trim()).filter(Boolean)
    let i = 0
    while (i < lines.length) {
      const isBullet = /^[-*]\s+/.test(lines[i])
      const run = []
      while (i < lines.length && /^[-*]\s+/.test(lines[i]) === isBullet) {
        run.push(lines[i])
        i++
      }
      if (isBullet) {
        elements.push(
          <ul key={key} style={{ margin: '4px 0 12px', paddingLeft: '20px' }}>
            {run.map((line, li) => (
              <li key={li} style={{ marginBottom: '4px' }}>
                {renderInline(line.replace(/^[-*]\s+/, ''), `${key}-${li}`)}
              </li>
            ))}
          </ul>
        )
      } else {
        elements.push(
          <p key={key} style={{ marginBottom: '12px' }}>
            {run.map((line, li) => (
              <span key={li}>
                {li > 0 && <br />}
                {renderInline(line, `${key}-${li}`)}
              </span>
            ))}
          </p>
        )
      }
      key++
    }
  }

  return elements
}

function Message({ role, text, citations, loading }) {
  const isUser = role === 'user'

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: isUser ? 'flex-end' : 'flex-start',
      marginBottom: '24px'
    }}>
      {/* Role label */}
      <span style={{
        fontSize: '11px', fontWeight: 600, letterSpacing: '0.5px',
        color: isUser ? 'var(--coral)' : 'var(--amber)',
        marginBottom: '6px',
        textTransform: 'uppercase'
      }}>
        {isUser ? 'You' : 'LoreFinder'}
      </span>

      {/* Bubble */}
      <div style={{
        maxWidth: '82%',
        background: isUser ? 'var(--coral-dim)' : 'var(--surface-raised)',
        border: `1px solid ${isUser ? 'rgba(255,107,87,0.2)' : 'var(--border)'}`,
        borderRadius: isUser
          ? 'var(--radius-lg) var(--radius-lg) var(--radius-sm) var(--radius-lg)'
          : 'var(--radius-lg) var(--radius-lg) var(--radius-lg) var(--radius-sm)',
        padding: '16px 20px'
      }}>
        {loading ? (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', color: 'var(--text-muted)', fontStyle: 'italic' }}>
            <LoadingSpinner size={14} color="var(--amber)" />
            Reading the text…
          </span>
        ) : (
          <div style={{
            color: 'var(--text-primary)', fontSize: '15px',
            lineHeight: 1.7
          }}>
            {renderFormattedText(text)}
          </div>
        )}
      </div>

      {/* Citations */}
      {!loading && citations && citations.length > 0 && (
        <div style={{ maxWidth: '82%', marginTop: '8px' }}>
          {citations.map((c, i) => (
            <CitationPill key={i} citation={c} />
          ))}
        </div>
      )}
    </div>
  )
}

export default function Query() {
  const { docId }               = useParams()
  const navigate                = useNavigate()
  const [messages, setMessages] = useState([])
  const [input, setInput]       = useState('')
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState('')
  const [meta, setMeta]         = useState(null)  // title + author from history
  const bottomRef               = useRef()
  const inputRef                = useRef()

  // Load metadata from history
  useEffect(() => {
    const history = getHistory()
    const entry   = history.find(h => h.doc_id === docId)
    if (entry) setMeta(entry)
  }, [docId])

  // Scroll to bottom on new message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function handleSend() {
    const q = input.trim()
    if (!q || loading) return

    setInput('')
    setError('')
    setMessages(prev => [...prev, { role: 'user', text: q }])
    setMessages(prev => [...prev, { role: 'assistant', text: '', citations: [], loading: true }])
    setLoading(true)

    try {
      const res = await queryDocument(docId, q)
        const responseText = res.response?.trim()
        ? res.response
        : "LoreFinder couldn't find a relevant answer in this document. Try rephrasing or asking something more specific."

        setMessages(prev => {
        const updated = [...prev]
        updated[updated.length - 1] = {
            role: 'assistant',
            text: responseText,
            citations: res.references || [],
            loading: false
        }
        return updated
        })
    } catch (e) {
      setMessages(prev => {
        const updated = [...prev]
        updated[updated.length - 1] = {
          role: 'assistant',
          text: e.message || 'Something went wrong. Please try again.',
          citations: [],
          loading: false,
          isError: true
        }
        return updated
      })
      setError(e.message)
    } finally {
      setLoading(false)
      setTimeout(() => inputRef.current?.focus(), 100)
    }
  }

  const suggestions = [
    'Summarize the main themes of this novel.',
    'Who is the protagonist and what drives them?',
    'Describe the opening chapter.',
  ]

  return (
    <div style={{
      display: 'flex', flexDirection: 'column',
      height: 'calc(100vh - 60px)'
    }}>
      {/* Doc header */}
      <div style={{
        background: 'var(--surface)',
        borderBottom: '1px solid var(--border)',
        padding: '14px 32px',
        display: 'flex', alignItems: 'center',
        justifyContent: 'space-between', flexShrink: 0
      }}>
        <div>
          <span style={{
            fontFamily: 'var(--font-display)',
            fontSize: '18px', fontWeight: 700,
            color: 'var(--text-primary)'
          }}>
            {meta?.title || 'Document'}
          </span>
          {meta?.author && (
            <span style={{ color: 'var(--text-secondary)', fontSize: '14px', marginLeft: '10px' }}>
              {meta.author}
            </span>
          )}
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span className={`tag ${meta?.type === 'pdf' ? 'tag-amber' : 'tag-sky'}`}>
            {meta?.type === 'pdf' ? 'PDF session' : 'Novel'}
          </span>
          <button
            className="btn-secondary"
            onClick={() => navigate('/')}
            style={{ padding: '7px 16px', fontSize: '13px' }}
          >
            ← New search
          </button>
        </div>
      </div>

      {/* Messages area */}
      <div style={{
        flex: 1, overflowY: 'auto',
        padding: '32px',
        maxWidth: '760px', width: '100%',
        margin: '0 auto', alignSelf: 'stretch'
      }}>
        {/* Empty state + suggestions */}
        {messages.length === 0 && (
          <div style={{ textAlign: 'center', marginTop: '48px' }}>
            <h3 style={{
              fontFamily: 'var(--font-display)',
              fontSize: '24px', marginBottom: '8px'
            }}>
              What would you like to know?
            </h3>
            <p className="muted" style={{ marginBottom: '32px' }}>
              Ask anything about{' '}
              <span style={{ color: 'var(--text-primary)' }}>
                {meta?.title || 'this document'}
              </span>
            </p>

            <div style={{
              display: 'flex', flexDirection: 'column',
              gap: '10px', maxWidth: '480px', margin: '0 auto'
            }}>
              {suggestions.map((s, i) => (
                <button
                  key={i}
                  onClick={() => { setInput(s); inputRef.current?.focus() }}
                  style={{
                    background: 'var(--surface)',
                    border: '1px solid var(--border)',
                    borderRadius: 'var(--radius-md)',
                    padding: '12px 18px',
                    color: 'var(--text-secondary)',
                    fontSize: '14px',
                    textAlign: 'left',
                    transition: 'border-color 0.2s, color 0.2s',
                    cursor: 'pointer'
                  }}
                  onMouseEnter={e => {
                    e.target.style.borderColor = 'var(--coral)'
                    e.target.style.color = 'var(--text-primary)'
                  }}
                  onMouseLeave={e => {
                    e.target.style.borderColor = 'var(--border)'
                    e.target.style.color = 'var(--text-secondary)'
                  }}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Messages */}
        {messages.map((msg, i) => (
          <Message
            key={i}
            role={msg.role}
            text={msg.text}
            citations={msg.citations}
            loading={msg.loading}
          />
        ))}

        <div ref={bottomRef} />
      </div>

      {/* Input bar */}
      <div style={{
        borderTop: '1px solid var(--border)',
        background: 'var(--surface)',
        padding: '16px 32px',
        flexShrink: 0
      }}>
        <div style={{
          maxWidth: '760px', margin: '0 auto',
          display: 'flex', gap: '12px', alignItems: 'flex-end'
        }}>
          <textarea
            ref={inputRef}
            className="input"
            placeholder="Ask anything about this novel…"
            value={input}
            rows={1}
            maxLength={2000}
            onChange={e => {
              setInput(e.target.value)
              // Auto-grow
              e.target.style.height = 'auto'
              e.target.style.height = Math.min(e.target.scrollHeight, 140) + 'px'
            }}
            onKeyDown={e => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleSend()
              }
            }}
            style={{
              resize: 'none', overflow: 'hidden',
              lineHeight: 1.5, padding: '12px 16px',
              minHeight: '46px'
            }}
          />
          <button
            className="btn-primary"
            onClick={handleSend}
            disabled={loading || !input.trim()}
            style={{
              padding: '12px 24px', flexShrink: 0,
              height: '46px', display: 'flex',
              alignItems: 'center', gap: '6px'
            }}
          >
            {loading ? '…' : 'Ask'}
          </button>
        </div>
        <p className="muted" style={{
          textAlign: 'center', fontSize: '12px', marginTop: '8px'
        }}>
          Press Enter to send · Shift+Enter for new line · Made by Swayam Bansal
        </p>
      </div>
    </div>
  )
}
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getHistory, removeFromHistory, clearHistory, checkStatus } from '../api/dawn'

function HistoryCard({ entry, onRemove, onOpen }) {
  const date = new Date(entry.added_at).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric'
  })

  return (
    <div
      className="card"
      style={{
        display: 'flex', alignItems: 'center',
        justifyContent: 'space-between', gap: '16px',
        padding: '20px 24px',
        transition: 'border-color 0.2s',
        cursor: 'pointer'
      }}
      onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--coral)'}
      onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--border)'}
      onClick={() => onOpen(entry.doc_id, entry.type)}
    >
      {/* Icon + text */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px', minWidth: 0 }}>
        <div style={{
          width: '44px', height: '44px', borderRadius: 'var(--radius-md)',
          background: entry.type === 'pdf' ? 'var(--amber-dim)' : 'var(--coral-dim)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '20px', flexShrink: 0
        }}>
          {entry.type === 'pdf' ? '📄' : '📖'}
        </div>

        <div style={{ minWidth: 0 }}>
          <p style={{
            fontFamily: 'var(--font-display)',
            fontSize: '16px', fontWeight: 700,
            color: 'var(--text-primary)',
            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'
          }}>
            {entry.title}
          </p>
          <p className="muted" style={{ fontSize: '13px', marginTop: '2px' }}>
            {entry.author} · {date}
          </p>
        </div>
      </div>

      {/* Right side */}
      <div
        style={{ display: 'flex', alignItems: 'center', gap: '10px', flexShrink: 0 }}
        onClick={e => e.stopPropagation()}
      >
        <span className={`tag ${entry.type === 'pdf' ? 'tag-amber' : 'tag-sky'}`}>
          {entry.type === 'pdf' ? 'PDF' : 'Novel'}
        </span>
        <button
          onClick={e => { e.stopPropagation(); onRemove(entry.doc_id) }}
          style={{
            background: 'transparent',
            border: '1px solid var(--border)',
            color: 'var(--text-muted)',
            borderRadius: 'var(--radius-sm)',
            padding: '5px 10px', fontSize: '12px',
            transition: 'border-color 0.2s, color 0.2s'
          }}
          onMouseEnter={e => {
            e.target.style.borderColor = 'var(--coral)'
            e.target.style.color = 'var(--coral)'
          }}
          onMouseLeave={e => {
            e.target.style.borderColor = 'var(--border)'
            e.target.style.color = 'var(--text-muted)'
          }}
        >
          Remove
        </button>
      </div>
    </div>
  )
}

export default function History() {
  const navigate              = useNavigate()
  const [entries, setEntries] = useState(getHistory())
  const [confirm, setConfirm] = useState(false)
  const [checking, setChecking] = useState(null) // doc_id being checked

  function handleRemove(docId) {
    removeFromHistory(docId)
    setEntries(getHistory())
  }

  function handleClear() {
    if (!confirm) { setConfirm(true); return }
    clearHistory()
    setEntries([])
    setConfirm(false)
  }

  async function handleOpen(docId, type) {
    // PDFs go straight to query — let it fail gracefully if session expired
    if (type === 'pdf') {
      navigate(`/query/${docId}`)
      return
    }

    setChecking(docId)
    try {
      const res = await checkStatus(docId)
      if (res.status === 'pending' || res.status === 'processing') {
        navigate(`/status/${docId}`)
      } else if (res.status === 'failed') {
        // Mark failed in local history then go home to retry
        navigate('/')
      } else {
        navigate(`/query/${docId}`)
      }
    } catch {
      // If status check fails, try query anyway
      navigate(`/query/${docId}`)
    } finally {
      setChecking(null)
    }
  }

  const novels = entries.filter(e => e.type === 'novel')
  const pdfs   = entries.filter(e => e.type === 'pdf')

  return (
    <div style={{ maxWidth: '720px', margin: '48px auto', padding: '0 24px' }}>

      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'flex-start',
        justifyContent: 'space-between', marginBottom: '36px'
      }}>
        <div>
          <h2 style={{ fontSize: '32px', marginBottom: '6px' }}>History</h2>
          <p className="muted">
            {entries.length === 0
              ? 'No documents yet.'
              : `${entries.length} document${entries.length > 1 ? 's' : ''} indexed`}
          </p>
        </div>

        {entries.length > 0 && (
          <button
            className="btn-secondary"
            onClick={handleClear}
            style={{
              padding: '8px 18px', fontSize: '13px',
              borderColor: confirm ? 'var(--coral)' : 'var(--border)',
              color: confirm ? 'var(--coral)' : 'var(--text-secondary)'
            }}
          >
            {confirm ? 'Confirm clear?' : 'Clear all'}
          </button>
        )}
      </div>

      {/* Loading indicator when checking status */}
      {checking && (
        <div style={{
          padding: '12px 16px', marginBottom: '16px',
          background: 'var(--sky-dim)', border: '1px solid rgba(78,168,222,0.2)',
          borderRadius: 'var(--radius-md)', fontSize: '14px', color: 'var(--sky)'
        }}>
          Checking status…
        </div>
      )}

      {/* Empty state */}
      {entries.length === 0 && (
        <div style={{
          textAlign: 'center', padding: '80px 24px',
          border: '1px dashed var(--border)',
          borderRadius: 'var(--radius-lg)'
        }}>
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>📚</div>
          <h3 style={{
            fontFamily: 'var(--font-display)',
            fontSize: '22px', marginBottom: '8px'
          }}>
            Nothing here yet
          </h3>
          <p className="muted" style={{ marginBottom: '24px' }}>
            Search for a novel or upload a PDF to get started.
          </p>
          <button className="btn-primary" onClick={() => navigate('/')}>
            Explore a novel
          </button>
        </div>
      )}

      {/* Novels section */}
      {novels.length > 0 && (
        <div style={{ marginBottom: '36px' }}>
          <p style={{
            fontSize: '12px', fontWeight: 600,
            color: 'var(--text-muted)', letterSpacing: '0.6px',
            marginBottom: '12px', textTransform: 'uppercase'
          }}>
            Novels
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {novels.map(entry => (
              <HistoryCard
                key={entry.doc_id}
                entry={entry}
                onRemove={handleRemove}
                onOpen={handleOpen}
              />
            ))}
          </div>
        </div>
      )}

      {/* PDFs section */}
      {pdfs.length > 0 && (
        <div>
          <p style={{
            fontSize: '12px', fontWeight: 600,
            color: 'var(--text-muted)', letterSpacing: '0.6px',
            marginBottom: '12px', textTransform: 'uppercase'
          }}>
            PDF Sessions
          </p>
          <p className="muted" style={{ fontSize: '13px', marginBottom: '12px' }}>
            PDF sessions expire after 2 hours of inactivity.
            Reopening a stale session will show an error.
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {pdfs.map(entry => (
              <HistoryCard
                key={entry.doc_id}
                entry={entry}
                onRemove={handleRemove}
                onOpen={handleOpen}
              />
            ))}
          </div>
        </div>
      )}

    </div>
  )
}
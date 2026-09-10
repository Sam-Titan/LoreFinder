import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { checkStatus } from '../api/dawn'

const PHASES = [
  { key: 'pending',    label: 'Queued',             desc: 'Waiting for a worker to pick up the task.' },
  { key: 'processing', label: 'Acquiring & parsing', desc: 'Finding the novel and extracting text.' },
  { key: 'ready',      label: 'Chunks indexed',      desc: 'Text is searchable. Summarizing chapters in background.' },
  { key: 'complete',   label: 'Fully indexed',       desc: 'Chapter summaries ready. Broad queries enabled.' },
]

function phaseIndex(status, progress) {
  if (progress === 'fully indexed') return 3
  if (status === 'ready')          return 2
  if (status === 'processing')     return 1
  return 0
}

export default function Status() {
  const { docId }             = useParams()
  const navigate              = useNavigate()
  const [data, setData]       = useState(null)
  const [error, setError]     = useState('')
  const [dots, setDots]       = useState('')

  // Animated dots
  useEffect(() => {
    const t = setInterval(() => setDots(d => d.length >= 3 ? '' : d + '.'), 500)
    return () => clearInterval(t)
  }, [])

  // Poll every 5 seconds
  useEffect(() => {
    let cancelled = false

    async function poll() {
      try {
        const res = await checkStatus(docId)
        if (cancelled) return
        setData(res)

        if (res.status === 'failed') {
          setError('Ingestion failed. Return home to try again.')
          return
        }

        // Redirect once chunks are ready — user can start narrow queries immediately
        if (res.status === 'ready' || res.status === 'complete') {
          setTimeout(() => navigate(`/query/${docId}`), 1200)
          return
        }

        setTimeout(poll, 5000)
      } catch (e) {
        if (!cancelled) setError(e.message)
      }
    }

    poll()
    return () => { cancelled = true }
  }, [docId, navigate])

  const current = data ? phaseIndex(data.status, data.progress) : 0

  return (
    <div style={{ maxWidth: '560px', margin: '64px auto', padding: '0 24px' }}>
      {/* Header */}
      <div style={{ marginBottom: '40px' }}>
        <span className="tag tag-amber" style={{ marginBottom: '12px' }}>Processing</span>
        <h2 style={{ fontSize: '28px', marginTop: '8px' }}>Indexing your novel</h2>
        <p className="muted" style={{ marginTop: '8px' }}>
          You'll be taken to the query page automatically once it's ready.
        </p>
      </div>

      {/* Phase tracker */}
      <div className="card" style={{ padding: '32px' }}>
        {PHASES.map((phase, i) => {
          const done    = i < current
          const active  = i === current
          const pending = i > current

          return (
            <div key={phase.key} style={{ display: 'flex', gap: '16px', marginBottom: i < PHASES.length - 1 ? '24px' : 0 }}>
              {/* Step indicator + connector */}
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                <div style={{
                  width: '32px', height: '32px',
                  borderRadius: '50%',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: '14px', fontWeight: 600, flexShrink: 0,
                  background: done    ? 'var(--coral)'          :
                              active  ? 'var(--coral-dim)'       : 'var(--base)',
                  border: `2px solid ${done || active ? 'var(--coral)' : 'var(--border)'}`,
                  color:  done        ? '#fff'                  :
                          active      ? 'var(--coral)'           : 'var(--text-muted)',
                  transition: 'all 0.4s'
                }}>
                  {done ? '✓' : i + 1}
                </div>
                {i < PHASES.length - 1 && (
                  <div style={{
                    width: '2px', flex: 1, marginTop: '6px',
                    background: done ? 'var(--coral)' : 'var(--border)',
                    minHeight: '24px', transition: 'background 0.4s'
                  }}/>
                )}
              </div>

              {/* Text */}
              <div style={{ paddingTop: '4px', paddingBottom: i < PHASES.length - 1 ? '24px' : 0 }}>
                <p style={{
                  fontWeight: 600, fontSize: '15px',
                  color: done || active ? 'var(--text-primary)' : 'var(--text-muted)'
                }}>
                  {phase.label}
                  {active && !error && <span style={{ color: 'var(--coral)' }}>{dots}</span>}
                </p>
                <p className="muted" style={{ marginTop: '2px', fontSize: '13px' }}>
                  {phase.desc}
                </p>
              </div>
            </div>
          )
        })}
      </div>

      {/* Error state */}
      {error && (
        <div style={{
          marginTop: '24px', padding: '16px 20px',
          background: 'var(--coral-dim)', border: '1px solid var(--coral)',
          borderRadius: 'var(--radius-md)'
        }}>
          <p style={{ color: 'var(--coral)', fontSize: '14px' }}>{error}</p>
          <button
            className="btn-secondary"
            onClick={() => navigate('/')}
            style={{ marginTop: '12px', padding: '8px 20px', fontSize: '13px' }}
          >
            Back to home
          </button>
        </div>
      )}

      {/* Doc ID reference */}
      {data && !error && (
        <p className="muted" style={{ marginTop: '20px', fontSize: '12px', textAlign: 'center' }}>
          Document ID: <code style={{ color: 'var(--sky)' }}>{docId}</code>
        </p>
      )}
    </div>
  )
}
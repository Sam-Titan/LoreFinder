import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { ingestNovel, ingestPDF, addToHistory } from '../api/dawn'

export default function Home() {
  const [mode, setMode]       = useState('novel') // 'novel' | 'pdf'
  const [title, setTitle]     = useState('')
  const [author, setAuthor]   = useState('')
  const [file, setFile]       = useState(null)
  const [dragging, setDragging] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState('')
  const fileRef               = useRef()
  const navigate              = useNavigate()

  async function handleNovelSubmit() {
    if (!title.trim() || !author.trim()) {
      setError('Please enter both title and author.')
      return
    }
    setError('')
    setLoading(true)
    try {
      const res = await ingestNovel(title.trim(), author.trim())
      addToHistory({
        doc_id: res.doc_id,
        title: title.trim(),
        author: author.trim(),
        type: 'novel',
        status: res.status
      })
      if (res.status === 'ready') {
        navigate(`/query/${res.doc_id}`)
      } else {
        navigate(`/status/${res.doc_id}`)
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function handlePDFSubmit() {
    if (!file) { setError('Please select a PDF file.'); return }
    setError('')
    setLoading(true)
    try {
      const res = await ingestPDF(file)
      addToHistory({
        doc_id: res.doc_id,
        title: file.name.replace('.pdf', ''),
        author: 'Uploaded PDF',
        type: 'pdf',
        status: res.status
      })
      navigate(`/status/${res.doc_id}`)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  function handleDrop(e) {
    e.preventDefault()
    setDragging(false)
    const dropped = e.dataTransfer.files[0]
    if (dropped && dropped.name.endsWith('.pdf')) {
      setFile(dropped)
      setError('')
    } else {
      setError('Only PDF files are supported.')
    }
  }

  return (
    <div>
      {/* Hero */}
      <div style={{
        background: 'linear-gradient(135deg, #0D1117 0%, #161B22 50%, #1a1428 100%)',
        borderBottom: '1px solid var(--border)',
        padding: '80px 32px 64px',
        textAlign: 'center',
        position: 'relative',
        overflow: 'hidden'
      }}>
        {/* Background glow */}
        <div style={{
          position: 'absolute', top: '-60px', left: '50%',
          transform: 'translateX(-50%)',
          width: '600px', height: '300px',
          background: 'radial-gradient(ellipse, rgba(255,107,87,0.08) 0%, transparent 70%)',
          pointerEvents: 'none'
        }}/>

        <h1 style={{
          fontFamily: 'var(--font-display)',
          fontSize: 'clamp(42px, 6vw, 72px)',
          fontWeight: 900,
          background: 'linear-gradient(90deg, var(--coral) 0%, var(--amber) 100%)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          marginBottom: '16px',
          letterSpacing: '-1px'
        }}>
          Every novel, answered.
        </h1>

        <p style={{
          color: 'var(--text-secondary)',
          fontSize: '18px',
          maxWidth: '520px',
          margin: '0 auto',
          lineHeight: 1.7
        }}>
          Find any public-domain novel or upload your own document.
          Ask anything — Dawn reads it so you don't have to start over.
        </p>
      </div>

      {/* Search card */}
      <div style={{ maxWidth: '560px', margin: '48px auto', padding: '0 24px' }}>
        <div className="card" style={{ padding: '32px' }}>

          {/* Mode toggle */}
          <div style={{
            display: 'flex',
            background: 'var(--base)',
            borderRadius: 'var(--radius-md)',
            padding: '4px',
            marginBottom: '28px'
          }}>
            {['novel', 'pdf'].map(m => (
              <button
                key={m}
                onClick={() => { setMode(m); setError('') }}
                style={{
                  flex: 1,
                  padding: '9px',
                  borderRadius: 'var(--radius-sm)',
                  border: 'none',
                  fontSize: '14px',
                  fontWeight: 500,
                  background: mode === m ? 'var(--surface-raised)' : 'transparent',
                  color: mode === m ? 'var(--text-primary)' : 'var(--text-muted)',
                  transition: 'all 0.2s'
                }}
              >
                {m === 'novel' ? '📖 Find a novel' : '📄 Upload PDF'}
              </button>
            ))}
          </div>

          {/* Novel form */}
          {mode === 'novel' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ fontSize: '13px', color: 'var(--text-secondary)', display: 'block', marginBottom: '6px' }}>
                  Title
                </label>
                <input
                  className="input"
                  placeholder="e.g. Frankenstein"
                  value={title}
                  onChange={e => setTitle(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleNovelSubmit()}
                />
              </div>
              <div>
                <label style={{ fontSize: '13px', color: 'var(--text-secondary)', display: 'block', marginBottom: '6px' }}>
                  Author
                </label>
                <input
                  className="input"
                  placeholder="e.g. Mary Shelley"
                  value={author}
                  onChange={e => setAuthor(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleNovelSubmit()}
                />
              </div>
              {error && <p className="error-text">{error}</p>}
              <button
                className="btn-primary"
                onClick={handleNovelSubmit}
                disabled={loading}
                style={{ marginTop: '8px', width: '100%' }}
              >
                {loading ? 'Searching…' : 'Find this novel'}
              </button>
              <p className="muted" style={{ textAlign: 'center' }}>
                Searches Project Gutenberg, Standard Ebooks, and Archive.org.
              </p>
            </div>
          )}

          {/* PDF form */}
          {mode === 'pdf' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div
                onClick={() => fileRef.current.click()}
                onDragOver={e => { e.preventDefault(); setDragging(true) }}
                onDragLeave={() => setDragging(false)}
                onDrop={handleDrop}
                style={{
                  border: `2px dashed ${dragging ? 'var(--coral)' : file ? 'var(--amber)' : 'var(--border)'}`,
                  borderRadius: 'var(--radius-md)',
                  padding: '40px 24px',
                  textAlign: 'center',
                  cursor: 'pointer',
                  background: dragging ? 'var(--coral-dim)' : file ? 'var(--amber-dim)' : 'var(--base)',
                  transition: 'all 0.2s'
                }}
              >
                <div style={{ fontSize: '32px', marginBottom: '8px' }}>
                  {file ? '✅' : '📂'}
                </div>
                <p style={{ color: file ? 'var(--amber)' : 'var(--text-secondary)', fontSize: '14px' }}>
                  {file ? file.name : 'Drop a PDF here or click to browse'}
                </p>
                {file && (
                  <p className="muted" style={{ marginTop: '4px' }}>
                    {(file.size / 1024 / 1024).toFixed(2)} MB
                  </p>
                )}
              </div>
              <input
                ref={fileRef}
                type="file"
                accept=".pdf"
                style={{ display: 'none' }}
                onChange={e => {
                  setFile(e.target.files[0])
                  setError('')
                }}
              />
              {error && <p className="error-text">{error}</p>}
              <button
                className="btn-primary"
                onClick={handlePDFSubmit}
                disabled={loading || !file}
                style={{ width: '100%' }}
              >
                {loading ? 'Uploading…' : 'Upload and index'}
              </button>
              <p className="muted" style={{ textAlign: 'center' }}>
                PDF is indexed for this session only — not stored permanently.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
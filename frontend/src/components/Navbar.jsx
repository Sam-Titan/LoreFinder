import { Link, useLocation } from 'react-router-dom'

export default function Navbar() {
  const { pathname } = useLocation()

  return (
    <nav style={{
      background: 'var(--surface)',
      borderBottom: '1px solid var(--border)',
      padding: '0 32px',
      height: '60px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      position: 'sticky',
      top: 0,
      zIndex: 100
    }}>
      <Link to="/" style={{ textDecoration: 'none' }}>
        <span style={{
          fontFamily: 'var(--font-display)',
          fontSize: '22px',
          fontWeight: 700,
          background: 'linear-gradient(90deg, var(--coral), var(--amber))',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent'
        }}>
          Dawn
        </span>
      </Link>

      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
        <NavLink to="/"        label="Explore"  active={pathname === '/'} />
        <NavLink to="/history" label="History"  active={pathname === '/history'} />
      </div>
    </nav>
  )
}

function NavLink({ to, label, active }) {
  return (
    <Link to={to} style={{
      padding: '6px 16px',
      borderRadius: 'var(--radius-md)',
      fontSize: '14px',
      fontWeight: 500,
      color: active ? 'var(--coral)' : 'var(--text-secondary)',
      background: active ? 'var(--coral-dim)' : 'transparent',
      transition: 'color 0.2s, background 0.2s',
      textDecoration: 'none'
    }}>
      {label}
    </Link>
  )
}
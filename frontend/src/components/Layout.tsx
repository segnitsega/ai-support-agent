import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'

export function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="shell">
      <header className="topbar">
        <NavLink to="/" className="brand">
          <span className="brand-mark" aria-hidden="true" />
          <span className="brand-text">
            <strong>Segni Electronics</strong>
            <span>Support</span>
          </span>
        </NavLink>
        <nav className="nav" aria-label="Primary">
          <NavLink to="/" end>
            Chat
          </NavLink>
          <NavLink to="/dashboard">Dashboard</NavLink>
        </nav>
      </header>
      <main className="main">{children}</main>
    </div>
  )
}

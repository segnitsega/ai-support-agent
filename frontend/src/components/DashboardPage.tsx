import { useCallback, useEffect, useState } from 'react'
import { getStats } from '../api/client'
import type { Stats } from '../api/types'

const EMPTY: Stats = {
  resolved_without_human: 0,
  escalations: 0,
  tickets_created: 0,
}

export function DashboardPage() {
  const [stats, setStats] = useState<Stats>(EMPTY)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setStats(await getStats())
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const total =
    stats.resolved_without_human + stats.escalations + stats.tickets_created
  const resolutionRate =
    total === 0
      ? 0
      : Math.round((stats.resolved_without_human / total) * 100)

  const cards = [
    {
      key: 'resolved',
      label: 'Resolved without human',
      value: stats.resolved_without_human,
      hint: 'FAQ answers and order lookups',
      accent: 'teal',
    },
    {
      key: 'escalations',
      label: 'Escalations',
      value: stats.escalations,
      hint: 'Handed off to a specialist',
      accent: 'amber',
    },
    {
      key: 'tickets',
      label: 'Tickets created',
      value: stats.tickets_created,
      hint: 'Approved Airtable tickets',
      accent: 'ink',
    },
  ] as const

  const maxBar = Math.max(
    1,
    stats.resolved_without_human,
    stats.escalations,
    stats.tickets_created,
  )

  return (
    <section className="dashboard-page">
      <header className="dashboard-header">
        <div>
          <h1>Operations dashboard</h1>
          <p>Live counts from completed agent runs.</p>
        </div>
        <button
          type="button"
          className="btn btn-ghost"
          onClick={() => void load()}
          disabled={loading}
        >
          {loading ? 'Refreshing…' : 'Refresh'}
        </button>
      </header>

      {error && <p className="error-banner">{error}</p>}

      <div className="stat-grid">
        {cards.map((card) => (
          <article key={card.key} className={`stat-card accent-${card.accent}`}>
            <p className="stat-label">{card.label}</p>
            <p className="stat-value">{loading ? '—' : card.value}</p>
            <p className="stat-hint">{card.hint}</p>
          </article>
        ))}
      </div>

      <article className="rate-panel">
        <div className="rate-copy">
          <p className="stat-label">Self-serve resolution rate</p>
          <p className="stat-value">{loading ? '—' : `${resolutionRate}%`}</p>
          <p className="stat-hint">
            Share of completed runs that did not escalate or open a ticket.
          </p>
        </div>
        <div className="bar-chart" aria-hidden={loading}>
          {cards.map((card) => (
            <div key={card.key} className="bar-row">
              <span>{card.label}</span>
              <div className="bar-track">
                <div
                  className={`bar-fill accent-${card.accent}`}
                  style={{
                    width: `${(card.value / maxBar) * 100}%`,
                  }}
                />
              </div>
              <strong>{card.value}</strong>
            </div>
          ))}
        </div>
      </article>
    </section>
  )
}

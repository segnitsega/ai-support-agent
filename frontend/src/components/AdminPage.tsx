import { useCallback, useEffect, useState } from 'react'
import { approve, listApprovals } from '../api/client'
import type { ApprovalItem, ApprovalStatus } from '../api/types'
import { MessageContent } from './MessageContent'

const FILTERS: Array<{ id: ApprovalStatus | 'all'; label: string }> = [
  { id: 'pending', label: 'Pending' },
  { id: 'approved', label: 'Approved' },
  { id: 'rejected', label: 'Rejected' },
  { id: 'all', label: 'All' },
]

function formatWhen(iso: string): string {
  try {
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(new Date(iso))
  } catch {
    return iso
  }
}

export function AdminPage() {
  const [filter, setFilter] = useState<ApprovalStatus | 'all'>('pending')
  const [items, setItems] = useState<ApprovalItem[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [acting, setActing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const selected = items.find((item) => item.thread_id === selectedId) ?? null

  const load = useCallback(async () => {
    setError(null)
    try {
      const rows = await listApprovals(filter)
      setItems(rows)
      setSelectedId((current) => {
        if (current && rows.some((row) => row.thread_id === current)) {
          return current
        }
        return rows[0]?.thread_id ?? null
      })
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setLoading(false)
    }
  }, [filter])

  useEffect(() => {
    setLoading(true)
    void load()
  }, [load])

  useEffect(() => {
    if (filter !== 'pending') return
    const timer = window.setInterval(() => {
      void load()
    }, 3000)
    return () => window.clearInterval(timer)
  }, [filter, load])

  async function resolve(approved: boolean) {
    if (!selected || selected.status !== 'pending' || acting) return
    setActing(true)
    setError(null)
    try {
      let finalAnswer = ''
      await approve(selected.thread_id, approved, (event, data) => {
        if (event === 'done') {
          finalAnswer = String(data.bot_answer ?? '')
        }
        if (event === 'error') {
          throw new Error(String(data.message ?? 'Approval failed'))
        }
      })
      setItems((prev) =>
        prev.map((item) =>
          item.thread_id === selected.thread_id
            ? {
                ...item,
                status: approved ? 'approved' : 'rejected',
                bot_answer: finalAnswer || item.bot_answer,
                resolved_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
              }
            : item,
        ),
      )
      await load()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setActing(false)
    }
  }

  return (
    <section className="admin-page">
      <header className="dashboard-header">
        <div>
          <h1>Ticket approvals</h1>
          <p>Review drafts paused by the agent before they hit Airtable.</p>
        </div>
        <button
          type="button"
          className="btn btn-ghost"
          onClick={() => void load()}
          disabled={loading || acting}
        >
          {loading ? 'Refreshing…' : 'Refresh'}
        </button>
      </header>

      <div className="filter-row" role="tablist" aria-label="Approval status">
        {FILTERS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={filter === tab.id}
            className={`filter-chip${filter === tab.id ? ' is-active' : ''}`}
            onClick={() => setFilter(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {error && <p className="error-banner">{error}</p>}

      <div className="admin-layout">
        <aside className="approval-list" aria-label="Approvals">
          {loading && items.length === 0 && (
            <p className="empty-copy">Loading approvals…</p>
          )}
          {!loading && items.length === 0 && (
            <p className="empty-copy">
              {filter === 'pending'
                ? 'No tickets waiting for review.'
                : 'No approvals in this view.'}
            </p>
          )}
          {items.map((item) => (
            <button
              key={item.thread_id}
              type="button"
              className={`approval-row${selectedId === item.thread_id ? ' is-selected' : ''}`}
              onClick={() => setSelectedId(item.thread_id)}
            >
              <div className="approval-row-top">
                <strong>{item.ticket.subject}</strong>
                <span className={`status-pill status-${item.status}`}>
                  {item.status}
                </span>
              </div>
              <p className="approval-preview">
                {item.user_question || item.ticket.description}
              </p>
              <time dateTime={item.created_at}>{formatWhen(item.created_at)}</time>
            </button>
          ))}
        </aside>

        <article className="approval-detail">
          {!selected && (
            <p className="empty-copy">Select a ticket to review its draft.</p>
          )}
          {selected && (
            <>
              <header className="approval-detail-header">
                <div>
                  <p className="eyebrow">Thread</p>
                  <h2>{selected.ticket.subject}</h2>
                </div>
                <span className={`status-pill status-${selected.status}`}>
                  {selected.status}
                </span>
              </header>

              <dl className="ticket-fields">
                <div>
                  <dt>Customer message</dt>
                  <dd>{selected.user_question || '—'}</dd>
                </div>
                <div>
                  <dt>Priority</dt>
                  <dd>
                    <span className={`priority priority-${selected.ticket.priority}`}>
                      {selected.ticket.priority}
                    </span>
                  </dd>
                </div>
                <div>
                  <dt>Customer email</dt>
                  <dd>{selected.ticket.customer_email}</dd>
                </div>
                <div className="ticket-description">
                  <dt>Draft description</dt>
                  <dd>{selected.ticket.description}</dd>
                </div>
                {selected.bot_answer && (
                  <div className="ticket-description">
                    <dt>Agent result</dt>
                    <dd>
                      <MessageContent text={selected.bot_answer} />
                    </dd>
                  </div>
                )}
                <div>
                  <dt>Created</dt>
                  <dd>{formatWhen(selected.created_at)}</dd>
                </div>
                {selected.resolved_at && (
                  <div>
                    <dt>Resolved</dt>
                    <dd>{formatWhen(selected.resolved_at)}</dd>
                  </div>
                )}
              </dl>

              {selected.status === 'pending' && (
                <footer className="modal-actions">
                  <button
                    type="button"
                    className="btn btn-ghost"
                    disabled={acting}
                    onClick={() => void resolve(false)}
                  >
                    Reject
                  </button>
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={acting}
                    onClick={() => void resolve(true)}
                  >
                    {acting ? 'Submitting…' : 'Approve & create'}
                  </button>
                </footer>
              )}
            </>
          )}
        </article>
      </div>
    </section>
  )
}

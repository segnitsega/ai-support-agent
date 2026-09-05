import type { TicketDraft } from '../api/types'

type Props = {
  ticket: TicketDraft
  busy: boolean
  onApprove: () => void
  onReject: () => void
}

export function ApprovalModal({ ticket, busy, onApprove, onReject }: Props) {
  return (
    <div className="modal-backdrop" role="presentation">
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="approval-title"
      >
        <header className="modal-header">
          <p className="eyebrow">Human approval required</p>
          <h2 id="approval-title">Create support ticket?</h2>
          <p className="modal-lead">
            Review the draft before it is written to Airtable.
          </p>
        </header>

        <dl className="ticket-fields">
          <div>
            <dt>Subject</dt>
            <dd>{ticket.subject}</dd>
          </div>
          <div>
            <dt>Priority</dt>
            <dd>
              <span className={`priority priority-${ticket.priority}`}>
                {ticket.priority}
              </span>
            </dd>
          </div>
          <div>
            <dt>Customer</dt>
            <dd>{ticket.customer_email}</dd>
          </div>
          <div className="ticket-description">
            <dt>Description</dt>
            <dd>{ticket.description}</dd>
          </div>
        </dl>

        <footer className="modal-actions">
          <button
            type="button"
            className="btn btn-ghost"
            disabled={busy}
            onClick={onReject}
          >
            Reject
          </button>
          <button
            type="button"
            className="btn btn-primary"
            disabled={busy}
            onClick={onApprove}
          >
            {busy ? 'Submitting…' : 'Approve'}
          </button>
        </footer>
      </div>
    </div>
  )
}

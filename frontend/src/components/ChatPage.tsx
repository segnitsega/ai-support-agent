import { useEffect, useId, useRef, useState, type FormEvent } from 'react'
import { approve, chat, toolStatusLabel } from '../api/client'
import type { ChatMessage, TicketDraft } from '../api/types'
import { ApprovalModal } from './ApprovalModal'

const EXAMPLES = [
  'What is your return policy?',
  'Where is my order #1234?',
  "Please open a ticket — my laptop won't turn on. Email me at you@example.com",
]

function newId() {
  return crypto.randomUUID()
}

export function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [statusText, setStatusText] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState<{
    threadId: string
    ticket: TicketDraft
  } | null>(null)

  const listRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)
  const inputId = useId()

  useEffect(() => {
    const el = listRef.current
    if (!el) return
    el.scrollTop = el.scrollHeight
  }, [messages, statusText, pending])

  useEffect(() => {
    return () => abortRef.current?.abort()
  }, [])

  function updateAssistant(id: string, patch: Partial<ChatMessage>) {
    setMessages((prev) =>
      prev.map((m) => (m.id === id ? { ...m, ...patch } : m)),
    )
  }

  function handleSse(
    event: string,
    data: Record<string, unknown>,
    assistantId: string,
  ) {
    switch (event) {
      case 'token': {
        const text = String(data.text ?? '')
        if (!text) return
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? { ...m, text: m.text + text, streaming: true }
              : m,
          ),
        )
        break
      }
      case 'tool_call_started': {
        setStatusText(toolStatusLabel(String(data.tool ?? 'tool')))
        break
      }
      case 'tool_call_result': {
        setStatusText('')
        break
      }
      case 'route': {
        const route = String(data.route ?? '')
        if (route === 'NEEDS_ORDER_LOOKUP') {
          setStatusText('Checking order details…')
        } else if (route === 'ANSWER_FROM_DOCS') {
          setStatusText('Searching help docs…')
        } else if (route === 'NEEDS_TICKET') {
          setStatusText('Drafting support ticket…')
        } else if (route === 'ESCALATE') {
          setStatusText('Escalating to a human agent…')
        }
        break
      }
      case 'approval_required': {
        const ticket = data.ticket as TicketDraft | undefined
        const threadId = String(data.thread_id ?? '')
        if (ticket && threadId) {
          setPending({ threadId, ticket })
          setStatusText('Waiting for ticket approval…')
        }
        break
      }
      case 'done': {
        const answer = String(data.bot_answer ?? '')
        const status = String(data.status ?? '')
        if (answer) {
          updateAssistant(assistantId, { text: answer, streaming: false })
        } else {
          updateAssistant(assistantId, { streaming: false })
        }
        if (status !== 'needs_approval') {
          setStatusText('')
        }
        break
      }
      case 'error': {
        setError(String(data.message ?? 'Something went wrong'))
        setStatusText('')
        break
      }
      default:
        break
    }
  }

  async function sendQuestion(question: string) {
    const trimmed = question.trim()
    if (!trimmed || busy || pending) return

    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    const userMsg: ChatMessage = {
      id: newId(),
      role: 'user',
      text: trimmed,
    }
    const assistantId = newId()
    const assistantMsg: ChatMessage = {
      id: assistantId,
      role: 'assistant',
      text: '',
      streaming: true,
    }

    setMessages((prev) => [...prev, userMsg, assistantMsg])
    setInput('')
    setError(null)
    setBusy(true)
    setStatusText('Thinking…')

    let awaitingApproval = false

    try {
      await chat(
        trimmed,
        (event, data) => {
          if (event === 'approval_required') awaitingApproval = true
          handleSse(event, data, assistantId)
        },
        controller.signal,
      )
      setMessages((prev) =>
        prev.map((m) => {
          if (m.id !== assistantId) return m
          if (awaitingApproval) {
            return {
              ...m,
              text: m.text || 'Ticket draft ready — please review and approve.',
              streaming: false,
            }
          }
          return {
            ...m,
            text: m.text || 'No response received.',
            streaming: false,
          }
        }),
      )
    } catch (err) {
      if ((err as Error).name === 'AbortError') return
      setError((err as Error).message)
      updateAssistant(assistantId, {
        text: 'Sorry — I could not complete that request.',
        streaming: false,
      })
      setStatusText('')
    } finally {
      setBusy(false)
    }
  }

  async function resolveApproval(approved: boolean) {
    if (!pending || busy) return
    const { threadId } = pending
    const assistantId = newId()

    setMessages((prev) => [
      ...prev,
      {
        id: assistantId,
        role: 'assistant',
        text: '',
        streaming: true,
      },
    ])
    setBusy(true)
    setError(null)
    setStatusText(approved ? 'Creating support ticket…' : 'Closing ticket draft…')
    setPending(null)

    const controller = new AbortController()
    abortRef.current = controller

    try {
      await approve(
        threadId,
        approved,
        (event, data) => handleSse(event, data, assistantId),
        controller.signal,
      )
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? {
                ...m,
                text: m.text || (approved ? 'Ticket approved.' : 'Ticket rejected.'),
                streaming: false,
              }
            : m,
        ),
      )
    } catch (err) {
      if ((err as Error).name === 'AbortError') return
      setError((err as Error).message)
      updateAssistant(assistantId, {
        text: 'Could not complete the approval step.',
        streaming: false,
      })
    } finally {
      setBusy(false)
      setStatusText('')
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    void sendQuestion(input)
  }

  return (
    <section className="chat-page">
      <div className="chat-panel">
        <header className="chat-header">
          <div>
            <h1>Support chat</h1>
            <p>Ask about policies, track an order, or open a ticket.</p>
          </div>
        </header>

        <div className="message-list" ref={listRef} aria-live="polite">
          {messages.length === 0 && (
            <div className="empty-state">
              <p className="empty-title">How can we help?</p>
              <p className="empty-copy">
                Try a sample question to see routing, tools, and human approval.
              </p>
              <ul className="example-list">
                {EXAMPLES.map((q) => (
                  <li key={q}>
                    <button
                      type="button"
                      className="example-chip"
                      disabled={busy}
                      onClick={() => void sendQuestion(q)}
                    >
                      {q}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {messages.map((m) => (
            <article
              key={m.id}
              className={`bubble bubble-${m.role}${m.streaming ? ' is-streaming' : ''}`}
            >
              <span className="bubble-label">
                {m.role === 'user' ? 'You' : 'Agent'}
              </span>
              <div className="bubble-body">
                {m.text || (m.streaming ? '…' : '')}
              </div>
            </article>
          ))}

          {statusText && (
            <div className="status-line" role="status">
              <span className="status-dot" aria-hidden="true" />
              {statusText}
            </div>
          )}
        </div>

        {error && <p className="error-banner">{error}</p>}

        <form className="composer" onSubmit={onSubmit}>
          <label className="sr-only" htmlFor={inputId}>
            Message
          </label>
          <textarea
            id={inputId}
            rows={2}
            value={input}
            disabled={busy || Boolean(pending)}
            placeholder={
              pending
                ? 'Approve or reject the ticket to continue…'
                : 'Ask a support question…'
            }
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                void sendQuestion(input)
              }
            }}
          />
          <button
            type="submit"
            className="btn btn-primary"
            disabled={busy || Boolean(pending) || !input.trim()}
          >
            Send
          </button>
        </form>
      </div>

      {pending && (
        <ApprovalModal
          ticket={pending.ticket}
          busy={busy}
          onApprove={() => void resolveApproval(true)}
          onReject={() => void resolveApproval(false)}
        />
      )}
    </section>
  )
}

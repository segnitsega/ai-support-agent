import { useEffect, useId, useRef, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { chat, getApproval, toolStatusLabel } from '../api/client'
import type { ChatMessage } from '../api/types'
import { MessageContent } from './MessageContent'

const EXAMPLES = [
  'What is your return policy?',
  'Where is my order #1234?',
  "Please open a ticket — my laptop won't turn on. Email me at you@example.com",
]

const WAITING_COPY =
  "I've prepared a support ticket draft. A specialist is reviewing it now — I'll update this chat when they finish."

function newId() {
  return crypto.randomUUID()
}

export function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [statusText, setStatusText] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [waitingThreadId, setWaitingThreadId] = useState<string | null>(null)
  const [waitingAssistantId, setWaitingAssistantId] = useState<string | null>(
    null,
  )

  const listRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)
  const inputId = useId()

  useEffect(() => {
    const el = listRef.current
    if (!el) return
    el.scrollTop = el.scrollHeight
  }, [messages, statusText, waitingThreadId])

  useEffect(() => {
    return () => abortRef.current?.abort()
  }, [])

  // Poll until an admin resolves the pending ticket for this thread.
  useEffect(() => {
    if (!waitingThreadId || !waitingAssistantId) return

    let cancelled = false
    const assistantId = waitingAssistantId
    const threadId = waitingThreadId

    async function pollOnce() {
      try {
        const item = await getApproval(threadId)
        if (cancelled || item.status === 'pending') return

        const fallback =
          item.status === 'approved'
            ? 'Your ticket was approved and created.'
            : 'Ticket creation was not approved. A human agent will follow up.'

        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? {
                  ...m,
                  text: item.bot_answer || fallback,
                  streaming: false,
                }
              : m,
          ),
        )
        setWaitingThreadId(null)
        setWaitingAssistantId(null)
        setStatusText('')
      } catch {
        // Keep waiting; queue row may lag the SSE pause briefly.
      }
    }

    void pollOnce()
    const timer = window.setInterval(() => {
      void pollOnce()
    }, 2500)

    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [waitingThreadId, waitingAssistantId])

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
        const threadId = String(data.thread_id ?? '')
        if (threadId) {
          setWaitingThreadId(threadId)
          setWaitingAssistantId(assistantId)
          setStatusText('Waiting for a specialist to review your ticket…')
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
    if (!trimmed || busy || waitingThreadId) return

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
              text: m.text || WAITING_COPY,
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
                      disabled={busy || Boolean(waitingThreadId)}
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
                <MessageContent
                  text={m.text}
                  streaming={m.streaming}
                  plain={m.role === 'user'}
                />
              </div>
            </article>
          ))}

          {waitingThreadId && (
            <div className="waiting-banner" role="status">
              <span className="status-dot" aria-hidden="true" />
              <div>
                <strong>Ticket under review</strong>
                <p>
                  A teammate will approve or reject it in{' '}
                  <Link to="/admin">Admin</Link>. This chat updates automatically.
                </p>
              </div>
            </div>
          )}

          {statusText && !waitingThreadId && (
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
            disabled={busy || Boolean(waitingThreadId)}
            placeholder={
              waitingThreadId
                ? 'Waiting for ticket review…'
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
            disabled={busy || Boolean(waitingThreadId) || !input.trim()}
          >
            Send
          </button>
        </form>
      </div>
    </section>
  )
}

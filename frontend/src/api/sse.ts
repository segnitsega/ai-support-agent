import type { SseHandler } from './types'

/**
 * Consume a POST endpoint that returns text/event-stream.
 * EventSource only supports GET, so we parse the stream manually.
 */
export async function streamSse(
  url: string,
  body: unknown,
  onEvent: SseHandler,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify(body),
    signal,
  })

  if (!response.ok) {
    let detail = `Request failed (${response.status})`
    try {
      const err = (await response.json()) as { detail?: string }
      if (err.detail) detail = err.detail
    } catch {
      /* ignore */
    }
    throw new Error(detail)
  }

  if (!response.body) {
    throw new Error('No response body from server')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const frames = buffer.split('\n\n')
    buffer = frames.pop() ?? ''

    for (const frame of frames) {
      dispatchFrame(frame, onEvent)
    }
  }

  if (buffer.trim()) {
    dispatchFrame(buffer, onEvent)
  }
}

function dispatchFrame(frame: string, onEvent: SseHandler): void {
  let eventName = 'message'
  const dataLines: string[] = []

  for (const rawLine of frame.split('\n')) {
    const line = rawLine.replace(/\r$/, '')
    if (!line || line.startsWith(':')) continue
    if (line.startsWith('event:')) {
      eventName = line.slice(6).trim()
      continue
    }
    if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trimStart())
    }
  }

  if (dataLines.length === 0) return

  const raw = dataLines.join('\n')
  try {
    const data = JSON.parse(raw) as Record<string, unknown>
    onEvent(eventName, data)
  } catch {
    onEvent(eventName, { raw })
  }
}

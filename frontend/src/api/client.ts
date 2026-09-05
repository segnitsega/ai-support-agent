import { streamSse } from './sse'
import type { SseHandler, Stats } from './types'

export function chat(question: string, onEvent: SseHandler, signal?: AbortSignal) {
  return streamSse('/chat', { question }, onEvent, signal)
}

export function approve(
  threadId: string,
  approved: boolean,
  onEvent: SseHandler,
  signal?: AbortSignal,
) {
  return streamSse('/approve', { thread_id: threadId, approved }, onEvent, signal)
}

export async function getStats(): Promise<Stats> {
  const response = await fetch('/stats')
  if (!response.ok) {
    throw new Error(`Failed to load stats (${response.status})`)
  }
  return response.json() as Promise<Stats>
}

export function toolStatusLabel(tool: string): string {
  switch (tool) {
    case 'get_order_status':
      return 'Looking up your order…'
    case 'create_ticket':
      return 'Creating support ticket…'
    default:
      return `Running ${tool}…`
  }
}

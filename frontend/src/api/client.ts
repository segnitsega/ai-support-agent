import { apiUrl } from './baseUrl'
import { streamSse } from './sse'
import type { ApprovalItem, ApprovalStatus, SseHandler, Stats } from './types'

export function chat(question: string, onEvent: SseHandler, signal?: AbortSignal) {
  return streamSse(apiUrl('/chat'), { question }, onEvent, signal)
}

export function approve(
  threadId: string,
  approved: boolean,
  onEvent: SseHandler,
  signal?: AbortSignal,
) {
  return streamSse(
    apiUrl('/approve'),
    { thread_id: threadId, approved },
    onEvent,
    signal,
  )
}

export async function getStats(): Promise<Stats> {
  const response = await fetch(apiUrl('/stats'))
  if (!response.ok) {
    throw new Error(`Failed to load stats (${response.status})`)
  }
  return response.json() as Promise<Stats>
}

export async function listApprovals(
  status: ApprovalStatus | 'all' = 'pending',
  limit = 50,
): Promise<ApprovalItem[]> {
  const params = new URLSearchParams({
    status,
    limit: String(limit),
  })
  const response = await fetch(apiUrl(`/approvals?${params}`))
  if (!response.ok) {
    throw new Error(`Failed to load approvals (${response.status})`)
  }
  return response.json() as Promise<ApprovalItem[]>
}

export async function getApproval(threadId: string): Promise<ApprovalItem> {
  const response = await fetch(
    apiUrl(`/approvals/${encodeURIComponent(threadId)}`),
  )
  if (!response.ok) {
    throw new Error(
      response.status === 404
        ? 'Approval not found.'
        : `Failed to load approval (${response.status})`,
    )
  }
  return response.json() as Promise<ApprovalItem>
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

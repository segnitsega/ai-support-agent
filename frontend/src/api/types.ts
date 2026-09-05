export type TicketDraft = {
  subject: string
  description: string
  priority: string
  customer_email: string
}

export type Stats = {
  resolved_without_human: number
  escalations: number
  tickets_created: number
}

export type ApprovalStatus = 'pending' | 'approved' | 'rejected'

export type ApprovalItem = {
  thread_id: string
  status: ApprovalStatus
  user_question: string
  route: string
  ticket: TicketDraft
  bot_answer: string
  created_at: string
  updated_at: string
  resolved_at: string | null
}

export type SseHandler = (event: string, data: Record<string, unknown>) => void

export type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  text: string
  streaming?: boolean
}

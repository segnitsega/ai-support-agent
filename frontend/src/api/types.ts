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

export type SseHandler = (event: string, data: Record<string, unknown>) => void

export type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  text: string
  streaming?: boolean
}

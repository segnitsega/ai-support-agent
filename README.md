# AI Support Agent

**A configurable AI customer-support agent for e-commerce and service businesses.**

This project is a production-shaped starter you can adapt to a client’s brand, policies, tools, and workflows, not a one-off chatbot demo. It answers from the company’s own knowledge base, looks up live order data, opens support tickets only after human approval, and escalates sensitive cases to staff.

Built for teams that want **automation with control**: the AI handles routine volume; people stay in the loop for anything that writes to external systems.

---

## Why clients hire this


| Outcome                       | What the agent does                                                                                     |
| ----------------------------- | ------------------------------------------------------------------------------------------------------- |
| Deflect repetitive tickets    | Answers policy / how-to questions from *your* docs (returns, shipping, warranty, account help)          |
| Resolve “where is my order?”  | Calls your order system (demo: local DB; replace with Shopify, WooCommerce, custom API)                 |
| Capture complex issues safely | Drafts a ticket, pauses for admin approval, then creates it in Airtable (or Zendesk / HubSpot / Linear) |
| Protect brand & risk          | Keyword + classifier escalations for legal threats, angry customers, “speak to a manager”               |
| Show ROI                      | Dashboard of self-serve resolutions, escalations, and tickets created                                   |


The same architecture works for **electronics, fashion, SaaS, clinics, logistics, or any business** with a help center + operational tools — swap the handbook, brand, and MCP tool backends.

---



## Live product surfaces


| Surface       | Audience                 | Purpose                                                               |
| ------------- | ------------------------ | --------------------------------------------------------------------- |
| **Chat**      | Customers                | Streaming answers, tool progress, “ticket under review” waiting state |
| **Admin**     | Support leads            | Queue of pending ticket drafts — Approve / Reject                     |
| **Dashboard** | Operators / stakeholders | Resolution, escalation, and ticket metrics                            |


---



## How it works (plain language)

1. The customer asks a question in chat.
2. The agent **classifies** the intent: answer from docs, look up an order, open a ticket, or escalate.
3. **Docs path** — retrieves relevant sections from your support handbook (RAG) and streams a grounded reply.
4. **Order path** — validates the order ID and calls an MCP tool for status.
5. **Ticket path** — drafts the ticket, stores it in an approvals queue, and **does not** write to Airtable until an admin approves.
6. **Escalate path** — hands off with a clear customer message when the issue needs a human.

That human-in-the-loop step is intentional: clients get speed without giving the model unsupervised write access.

---



## What can be customized per client


| Layer              | Examples                                                                              |
| ------------------ | ------------------------------------------------------------------------------------- |
| **Brand & copy**   | Company name, tone, UI labels, contact channels                                       |
| **Knowledge base** | Replace `segni_support_handbook.md` with the client’s policies; re-ingest to Pinecone |
| **Routing rules**  | Escalation keywords, route categories, structured ticket fields                       |
| **Tools (MCP)**    | Order lookup → their OMS; tickets → Zendesk, Freshdesk, HubSpot, Notion, Slack        |
| **Models**         | Gemini today; LangChain makes swapping providers straightforward                      |
| **Auth & hosting** | Lock Admin behind login; deploy API + UI on the client’s stack                        |


---



## Tech stack

**Backend:** Python, FastAPI (SSE streaming), LangGraph, LangChain, Gemini, Pinecone, MCP, Pydantic, SQLite (stats + approvals)  
**Frontend:** React (Vite), React Router, Markdown rendering for agent replies  
**Integrations (demo):** Airtable tickets, local SQLite orders

---



## Project layout

```
backend/                  # FastAPI + LangGraph agent + RAG + MCP
  app/graph/              # Routing, RAG, tools, human approval interrupt
  app/mcp/                # Order lookup & Airtable ticket servers
  app/rag/                # Chunk → embed → Pinecone ingest / retrieve
  data/faq_docs/          # Client support handbook (Markdown)
frontend/                 # Chat, Admin, Dashboard
```

---



## Quick start



### Prerequisites

- Python 3.13+ and [uv](https://github.com/astral-sh/uv)  
- Node.js 20+  
- API keys: Google Gemini, Pinecone, Airtable (for ticket creation)



### Backend

```bash
cd backend
cp .example.env .env   # fill in keys
uv sync
uv run python -m app.rag ingest --embed-batch-delay 0
uv run fastapi dev     # http://127.0.0.1:8000
```



### Frontend

```bash
cd frontend
npm install
npm run dev            # http://127.0.0.1:5173
```

Vite proxies `/chat`, `/approve`, `/approvals`, and `/stats` to the API.

### Docker (recommended for demos / client handoff)

Requires Docker + Compose, and a filled `backend/.env`.

```bash
# from repo root
docker compose up --build
```

- **App UI:** http://127.0.0.1:8080  
- **API (direct):** http://127.0.0.1:8000  

First-time helpers (optional):

```bash
# seed demo orders into the mounted SQLite volume
docker compose exec api uv run python -m app.mcp.seed_orders

# ingest / refresh the support handbook into Pinecone
docker compose exec api uv run python -m app.rag ingest --embed-batch-delay 0
```

See the Docker layout notes below for what each file does.

### Demo script (client walkthrough)

1. **Policy:** “What is your return policy?” → streaming RAG answer
2. **Order:** “Where is my order #1234?” → tool lookup
3. **Ticket:** “Open a ticket — my laptop won’t turn on…” → chat waits; **Admin** approves → Airtable row
4. **Escalate:** “I want to file a lawsuit” → human handoff
5. **Dashboard** → counts updated

---



## API (for integration work)


| Method | Path         | Notes                                                            |
| ------ | ------------ | ---------------------------------------------------------------- |
| `POST` | `/chat`      | SSE stream (`token`, `tool_call_*`, `approval_required`, `done`) |
| `POST` | `/approve`   | Resume paused ticket (`thread_id`, `approved`)                   |
| `GET`  | `/approvals` | Admin queue (`?status=pending`)                                  |
| `GET`  | `/stats`     | Dashboard metrics                                                |


---

## Docker layout

| File | Role |
| --- | --- |
| `backend/Dockerfile` | Python 3.13 image: installs deps with `uv`, runs uvicorn |
| `frontend/Dockerfile` | Multi-stage: `npm run build`, then nginx serves `dist/` |
| `frontend/nginx.conf` | SPA routing + reverse-proxy of `/chat`, `/approve`, `/stats`, `/approvals` to the `api` service (SSE buffering off) |
| `docker-compose.yml` | Starts `api` + `web`, mounts `backend/data` for SQLite + handbook, loads `backend/.env` |

The nginx container replaces the Vite **dev** proxy: the browser only talks to port **8080**; API calls stay same-origin.

---



## Engagement options

Typical scopes clients ask for:

1. **Pilot & configure** — brand, handbook ingest, tools pointed at their systems
2. **Extend** — more routes, CRM sync, auth, multi-language, channel adapters (WhatsApp, Intercom widget)
3. **Harden** — durable checkpointers, audit logs, eval set for routing quality, rate-limit UX

If you are a business evaluating this: the demo store (**Segni Electronics**) is a stand-in. Your policies and tools plug into the same agent loop.

---



## License / ownership

Private project source — available under agreement for client delivery and customization.

---

*Questions or want this adapted to your stack? Open an issue or reach out with your help-center URL and the systems you use for orders and tickets.*
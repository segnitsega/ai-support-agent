# AI Support Agent

**A configurable AI customer-support agent for e-commerce and service businesses.**

[**Live demo →**](https://customer-support-agent-7kk1.onrender.com/)

This project is a production-shaped starter you can adapt to a company’s brand, policies, tools, and workflows — not a one-off chatbot toy. It answers from the company’s own knowledge base, looks up live order data, opens support tickets only after human approval, and escalates sensitive cases to staff.

Built for teams that want **automation with control**: the AI handles routine volume; people stay in the loop for anything that writes to external systems.

---

## Why businesses need this

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

Try them on the [live demo](https://customer-support-agent-7kk1.onrender.com/).

---

## How it works (plain language)

1. The customer asks a question in chat.
2. The agent **classifies** the intent: answer from docs, look up an order, open a ticket, or escalate.
3. **Docs path** — retrieves relevant sections from your support handbook (RAG) and streams a grounded reply.
4. **Order path** — validates the order ID and calls an MCP tool for status.
5. **Ticket path** — drafts the ticket, stores it in an approvals queue, and **does not** write to Airtable until an admin approves.
6. **Escalate path** — hands off with a clear customer message when the issue needs a human.

That human-in-the-loop step is intentional: the business gets speed without giving the model unsupervised write access.

---

## What you can customize

| Layer              | Examples                                                                              |
| ------------------ | ------------------------------------------------------------------------------------- |
| **Brand & copy**   | Company name, tone, UI labels, contact channels                                       |
| **Knowledge base** | Replace `segni_support_handbook.md` with your policies; re-ingest to Pinecone         |
| **Routing rules**  | Escalation keywords, route categories, structured ticket fields                       |
| **Tools (MCP)**    | Order lookup → your OMS; tickets → Zendesk, Freshdesk, HubSpot, Notion, Slack         |
| **Models**         | Gemini today; LangChain makes swapping providers straightforward                      |
| **Auth & hosting** | Lock Admin behind login; deploy API + UI on your stack                                |

---

## Tech stack

**Backend:** Python, FastAPI (SSE streaming), LangGraph, LangChain, Gemini, Pinecone, MCP, Pydantic, SQLite (stats + approvals)  
**Frontend:** React (Vite), React Router, Markdown rendering for agent replies  
**Integrations (demo):** Airtable tickets, local SQLite orders  
**Packaging:** Docker + Docker Compose (API and UI as separate services)

---

## Project layout

```
backend/                  # FastAPI + LangGraph agent + RAG + MCP
  app/graph/              # Routing, RAG, tools, human approval interrupt
  app/mcp/                # Order lookup & Airtable ticket servers
  app/rag/                # Chunk → embed → Pinecone ingest / retrieve
  data/faq_docs/          # Support handbook (Markdown)
frontend/                 # Chat, Admin, Dashboard
docker-compose.yml        # Local full stack (api + web)
```

---

## Quick start (Docker)

Requires [Docker](https://docs.docker.com/get-docker/) + Compose, and a filled `backend/.env`.

```bash
cd backend
cp .example.env .env   # fill in Google, Pinecone, Airtable keys
cd ..

docker compose up --build
```

Use `--build` whenever Dockerfiles or frontend source change so images stay current.

| Service | URL |
| --- | --- |
| **App UI** | http://127.0.0.1:8080 |
| **API** | http://127.0.0.1:8000 |

The UI container gets `VITE_API_URL=http://127.0.0.1:8000` so the browser calls the API directly (CORS is enabled on FastAPI).

First-time helpers (optional):

```bash
# seed demo orders into the mounted SQLite volume
docker compose exec api uv run python -m app.mcp.seed_orders

# ingest / refresh the support handbook into Pinecone
docker compose exec api uv run python -m app.rag ingest --embed-batch-delay 0
```

### Demo script (walkthrough)

1. **Policy:** “What is your return policy?” → streaming RAG answer  
2. **Order:** “Where is my order #1234?” → tool lookup  
3. **Ticket:** “Open a ticket — my laptop won’t turn on…” → chat waits; **Admin** approves → Airtable row  
4. **Escalate:** “I want to file a lawsuit” → human handoff  
5. **Dashboard** → counts updated  

---

## Deploy (Render)

Deploy **two** Docker web services from this repo:

| Service | Root directory | Runtime notes |
| --- | --- | --- |
| **API** | `backend` | Set secrets from `.example.env`. Attach a disk at `/app/data` if you want SQLite to survive redeploys. |
| **Web** | `frontend` | Set `VITE_API_URL` to the API’s public URL (e.g. `https://YOUR-API.onrender.com`), no trailing slash. |

---

## API

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
| `backend/Dockerfile` | Python 3.13: `uv sync`, runs uvicorn on port 8000 |
| `frontend/Dockerfile` | Multi-stage: `npm run build`, then `serve` hosts `dist/` on `$PORT` |
| `frontend/docker-entrypoint.sh` | Writes `dist/config.js` from `VITE_API_URL`, starts `serve` (SPA mode) |
| `docker-compose.yml` | Starts `api` + `web`, mounts `backend/data`, loads `backend/.env` |

---

## Local dev without Docker (optional)

**Prerequisites:** Python 3.13+, [uv](https://github.com/astral-sh/uv), Node.js 20+.

```bash
# API
cd backend
cp .example.env .env
uv sync
uv run python -m app.rag ingest --embed-batch-delay 0
uv run fastapi dev     # http://127.0.0.1:8000

# UI (separate terminal)
cd frontend
npm install
npm run dev            # http://127.0.0.1:5173 — Vite proxies API paths to :8000
```

---

## Extending this project

Common next steps:

1. **Configure** — brand, handbook ingest, tools pointed at your systems  
2. **Extend** — more routes, CRM sync, auth, multi-language, channel adapters (WhatsApp, Intercom widget)  
3. **Harden** — durable checkpointers, audit logs, eval set for routing quality, rate-limit UX  

The demo store (**Segni Electronics**) is a stand-in. Your policies and tools plug into the same agent loop.

---

## License

Private project source.

---

*Questions or ideas? Open an issue with your help-center URL and the systems you use for orders and tickets.*

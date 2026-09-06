from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langgraph.types import Command
from pydantic import BaseModel, Field

from app.approvals import (
    get_approval,
    init_db as init_approvals_db,
    list_approvals,
    resolve_approval,
    upsert_pending,
)
from app.graph.main import _answer_text, app as agent
from app.mcp.orders_db import seed_orders
from app.stats import get_stats, init_db as init_stats_db, record_run

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}

TOKEN_NODES = {"rag_node"}


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    thread_id: str | None = None


class ApproveRequest(BaseModel):
    thread_id: str
    approved: bool


class StatsResponse(BaseModel):
    resolved_without_human: int
    escalations: int
    tickets_created: int


class TicketDraft(BaseModel):
    subject: str
    description: str
    priority: str
    customer_email: str


class ApprovalItem(BaseModel):
    thread_id: str
    status: Literal["pending", "approved", "rejected"]
    user_question: str
    route: str
    ticket: TicketDraft
    bot_answer: str = ""
    created_at: str
    updated_at: str
    resolved_at: str | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_stats_db()
    init_approvals_db()
    # Demo orders — same seed the order MCP server applies, but at API boot
    # so Render / cold starts are ready before the first order lookup.
    order_count = seed_orders(reset=False)
    print(f"[startup] demo orders ready ({order_count} row(s))")
    yield


app = FastAPI(
    title="Segni Electronics Support Agent",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "Hello World!"}


@app.get("/stats", response_model=StatsResponse)
async def stats():
    return get_stats()


@app.get("/approvals", response_model=list[ApprovalItem])
async def approvals(
    status: Literal["pending", "approved", "rejected", "all"] = Query("pending"),
    limit: int = Query(50, ge=1, le=200),
):
    return list_approvals(status=status, limit=limit)


@app.get("/approvals/{thread_id}", response_model=ApprovalItem)
async def approval_detail(thread_id: str):
    row = get_approval(thread_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Approval not found.")
    return row


@app.post("/chat")
async def chat(body: ChatRequest):
    thread_id = body.thread_id or str(uuid.uuid4())
    return _sse_response(_stream_run({"user_question": body.question}, thread_id))


@app.post("/approve")
async def approve(body: ApproveRequest):
    config = {"configurable": {"thread_id": body.thread_id}}
    snapshot = agent.get_state(config)
    if not snapshot.next:
        raise HTTPException(
            status_code=409,
            detail="No pending ticket approval for this thread_id.",
        )

    queued = get_approval(body.thread_id)
    if queued is not None and queued["status"] != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Approval already resolved as {queued['status']}.",
        )

    resume = "approved" if body.approved else "rejected"
    return _sse_response(
        _stream_run(
            Command(resume=resume),
            body.thread_id,
            approval_decision="approved" if body.approved else "rejected",
        )
    )


def _sse_response(events: AsyncIterator[tuple[str, dict]]) -> StreamingResponse:
    return StreamingResponse(
        _encode_sse(events),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


async def _encode_sse(events: AsyncIterator[tuple[str, dict]]) -> AsyncIterator[str]:
    try:
        async for event, data in events:
            yield _sse(event, data)
    except Exception as exc:
        print(f"[api] stream error: {exc}")
        yield _sse(
            "error",
            {
                "message": _public_error_message(exc),
                "code": _error_code(exc),
            },
        )


def _error_code(exc: BaseException) -> str:
    text = str(exc).lower()
    if any(
        token in text
        for token in (
            "resource_exhausted",
            "429",
            "quota",
            "rate limit",
            "ratelimit",
        )
    ):
        return "rate_limited"
    if any(token in text for token in ("api key", "unauthenticated", "401", "403")):
        return "auth"
    if any(token in text for token in ("timeout", "timed out", "deadline")):
        return "timeout"
    return "internal"


def _public_error_message(exc: BaseException) -> str:
    """Map provider/infra failures to short user-facing copy."""
    code = _error_code(exc)
    if code == "rate_limited":
        return (
            "We're getting a lot of requests right now. "
            "Please wait a moment and try again."
        )
    if code == "auth":
        return "The support service is temporarily unavailable. Please try again later."
    if code == "timeout":
        return "That took too long to answer. Please try again."
    return "Something went wrong while processing your request. Please try again."


async def _stream_run(
    graph_input: dict | Command,
    thread_id: str,
    *,
    approval_decision: Literal["approved", "rejected"] | None = None,
) -> AsyncIterator[tuple[str, dict]]:
    config = {"configurable": {"thread_id": thread_id}}
    seen_nodes: set[str] = set()
    interrupted_payload: dict | None = None

    yield "start", {"thread_id": thread_id}

    async for part in _aiter_graph(graph_input, config):
        mapped = _map_stream_part(part, seen_nodes)
        if mapped is None:
            continue
        event, data = mapped
        if event == "approval_required":
            data = {**data, "thread_id": thread_id}
            interrupted_payload = data
        yield event, data

    snapshot = agent.get_state(config)
    public = _public_state(snapshot.values)
    pending = bool(snapshot.next)

    if pending and interrupted_payload is None:
        interrupted_payload = _interrupt_from_snapshot(snapshot)
        if interrupted_payload:
            yield "approval_required", {**interrupted_payload, "thread_id": thread_id}

    if pending:
        ticket = None
        if interrupted_payload and isinstance(interrupted_payload.get("ticket"), dict):
            ticket = interrupted_payload["ticket"]
        elif isinstance(public.get("pending_ticket"), dict):
            ticket = public["pending_ticket"]
        if ticket:
            upsert_pending(
                thread_id=thread_id,
                ticket=ticket,
                user_question=str(public.get("user_question") or ""),
                route=str(public.get("question_type") or ""),
            )
    elif approval_decision is not None:
        resolve_approval(
            thread_id=thread_id,
            status=approval_decision,
            bot_answer=str(public.get("bot_answer") or ""),
        )

    status: Literal["completed", "needs_approval"] = (
        "needs_approval" if pending else "completed"
    )
    if not pending:
        outcome = _outcome(public.get("question_type") or "", seen_nodes)
        record_run(
            thread_id=thread_id,
            route=public.get("question_type") or "",
            outcome=outcome,
        )

    yield "done", {
        "thread_id": thread_id,
        "status": status,
        "route": public.get("question_type") or "",
        "bot_answer": public.get("bot_answer") or "",
        "pending_ticket": public.get("pending_ticket"),
    }


def _aiter_graph(
    graph_input: dict | Command,
    config: dict,
) -> AsyncIterator[Any]:
    """Run the sync graph.stream() in a worker thread so MCP asyncio.run() is safe."""
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    sentinel = object()

    def produce() -> None:
        try:
            for part in _sync_stream(graph_input, config):
                loop.call_soon_threadsafe(queue.put_nowait, part)
        except Exception as exc:
            loop.call_soon_threadsafe(queue.put_nowait, exc)
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, sentinel)

    loop.run_in_executor(None, produce)

    async def consume() -> AsyncIterator[Any]:
        while True:
            item = await queue.get()
            if item is sentinel:
                return
            if isinstance(item, Exception):
                raise item
            yield item

    return consume()


def _sync_stream(graph_input: dict | Command, config: dict) -> Iterator[Any]:
    return agent.stream(
        graph_input,
        config,
        stream_mode=["messages", "updates", "custom"],
        version="v2",
    )


def _map_stream_part(
    part: dict,
    seen_nodes: set[str],
) -> tuple[str, dict] | None:
    kind = part.get("type")
    data = part.get("data")

    if kind == "messages":
        message, metadata = data
        node = (metadata or {}).get("langgraph_node") or ""
        if node not in TOKEN_NODES:
            return None
        text = _answer_text(getattr(message, "content", ""))
        if not text:
            return None
        return "token", {"text": text, "node": node}

    if kind == "custom" and isinstance(data, dict):
        payload = dict(data)
        event = payload.pop("event", "custom")
        return event, payload

    if kind == "updates" and isinstance(data, dict):
        interrupt_payload = _interrupt_from_updates(data)
        if interrupt_payload is not None:
            return "approval_required", interrupt_payload

        classify = data.get("classify")
        if isinstance(classify, dict) and classify.get("question_type"):
            seen_nodes.add("classify")
            return "route", {"route": classify["question_type"]}

        for node_name in data:
            if not str(node_name).startswith("__"):
                seen_nodes.add(node_name)

    return None


def _interrupt_from_updates(data: dict) -> dict | None:
    interrupts = data.get("__interrupt__")
    if not interrupts:
        return None
    first = interrupts[0]
    value = getattr(first, "value", None)
    if value is None and isinstance(first, dict):
        value = first.get("value")
    if isinstance(value, dict):
        return value
    if value is None:
        return None
    return {"payload": value}


def _interrupt_from_snapshot(snapshot) -> dict | None:
    for task in snapshot.tasks or ():
        for item in task.interrupts or ():
            value = getattr(item, "value", None)
            if isinstance(value, dict):
                return value
    return None


def _public_state(values: Any) -> dict:
    if hasattr(values, "bot_answer"):
        return {
            "bot_answer": values.bot_answer or "",
            "question_type": values.question_type or "",
            "pending_ticket": values.pending_ticket,
            "user_question": getattr(values, "user_question", "") or "",
        }
    if isinstance(values, dict):
        return {
            "bot_answer": values.get("bot_answer") or "",
            "question_type": values.get("question_type") or "",
            "pending_ticket": values.get("pending_ticket"),
            "user_question": values.get("user_question") or "",
        }
    return {
        "bot_answer": "",
        "question_type": "",
        "pending_ticket": None,
        "user_question": "",
    }


def _outcome(route: str, seen_nodes: set[str]) -> str:
    if "execute_ticket" in seen_nodes:
        return "ticket_created"
    if "reject_ticket" in seen_nodes or route == "ESCALATE":
        return "escalated"
    return "resolved_without_human"


def _sse(event: str, data: dict) -> str:
    payload = json.dumps(data, default=str, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"

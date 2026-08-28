from typing import Literal

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from app.rag import retrieve

load_dotenv()

Route = Literal[
    "ANSWER_FROM_DOCS",
    "NEEDS_ORDER_LOOKUP",
    "NEEDS_TICKET",
    "ESCALATE",
]

# Hard guardrail: force escalation regardless of LLM classification.
ESCALATE_KEYWORDS = [
    "lawsuit",
    "lawyer",
    "cancel my account",
    "delete my account",
    "speak to a manager",
    "human agent",
    "complaint",
]

CLASSIFY_PROMPT = """You route customer support messages for Segni Electronics.

Choose exactly one route:
- ANSWER_FROM_DOCS: policy/how-to questions answerable from FAQ docs
  (returns, shipping policy, payment methods, password reset, etc.)
- NEEDS_ORDER_LOOKUP: user wants status/info about a specific order
  (track order, where is my order, order #1234)
- NEEDS_TICKET: user wants support to open a ticket for an unresolved issue
- ESCALATE: angry user, legal threat, or explicit request for a human agent

User message:
{question}
"""


class RouteDecision(BaseModel):
    route: Route = Field(description="The routing category for this message.")


class AgentState(BaseModel):
    user_question: str = ""
    bot_answer: str = ""
    retrieve_result: list[Document] = []
    question_type: Route | str = ""


rag_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a customer support assistant for Segni Electronics. "
        "Answer using only the provided context. If the context is insufficient, say so.",
    ),
    (
        "human",
        "Context:\n{context}\n\nQuestion:\n{question}",
    ),
])

llm = init_chat_model("google_genai:gemini-3.5-flash")
classifier = llm.with_structured_output(RouteDecision)


def classify_node(state: AgentState) -> dict:
    """Classify the user message and store the route on state."""
    question = state.user_question.strip()
    lowered = question.lower()

    for keyword in ESCALATE_KEYWORDS:
        if keyword in lowered:
            print(f"[route] keyword guardrail → ESCALATE (matched: {keyword!r})")
            return {"question_type": "ESCALATE"}

    decision = classifier.invoke(
        CLASSIFY_PROMPT.format(question=question),
    )
    route = decision.route
    print(f"[route] classifier → {route}")
    return {"question_type": route}


def route_by_type(state: AgentState) -> str:
    """Read question_type from state and return the next node name."""
    route = state.question_type
    if route not in {
        "ANSWER_FROM_DOCS",
        "NEEDS_ORDER_LOOKUP",
        "NEEDS_TICKET",
        "ESCALATE",
    }:
        print(f"[route] unknown route {route!r}, defaulting to ESCALATE")
        return "ESCALATE"
    return route


def retrieve_node(state: AgentState) -> dict:
    """Retrieve FAQ chunks for RAG answers."""
    docs = retrieve(state.user_question)
    print(f"[retrieve] found {len(docs)} chunk(s)")
    return {"retrieve_result": docs}


def answer_from_docs(state: AgentState) -> dict:
    """Generate an answer grounded in retrieved FAQ chunks."""
    context = "\n\n".join(doc.page_content for doc in state.retrieve_result)
    messages = rag_prompt.format_messages(
        context=context or "No relevant documents found.",
        question=state.user_question,
    )
    response = llm.invoke(messages)
    return {"bot_answer": _answer_text(response.content)}


def order_lookup(state: AgentState) -> dict:
    """Stub: fake order lookup until MCP is wired in Stage 4."""
    print("[node] order_lookup (stub)")
    return {
        "bot_answer": (
            "I looked up your order #1234 (stub). Status: out for delivery, "
            "expected today by 6 PM. Reply with your order number for a real lookup in Stage 4."
        ),
    }


def book_ticket(state: AgentState) -> dict:
    """Stub: fake ticket creation until Airtable MCP is wired in Stage 4."""
    print("[node] book_ticket (stub)")
    return {
        "bot_answer": (
            "I've prepared a support ticket for your issue (stub). "
            "Ticket draft: subject='Customer issue', priority='normal'. "
            "Human approval + Airtable integration comes in Stage 4–5."
        ),
    }


def escalate(state: AgentState) -> dict:
    """Escalate to a human agent."""
    print("[node] escalation")
    return {
        "bot_answer": (
            "I'm connecting you with a Segni Electronics support specialist. "
            "Please hold — a human agent will assist you shortly."
        ),
    }


graph = StateGraph(AgentState)

graph.add_node("classify", classify_node)
graph.add_node("retrieve", retrieve_node)
graph.add_node("rag_node", answer_from_docs)
graph.add_node("order_lookup", order_lookup)
graph.add_node("book_ticket", book_ticket)
graph.add_node("escalation", escalate)

graph.add_edge(START, "classify")
graph.add_conditional_edges(
    "classify",
    route_by_type,
    {
        "ANSWER_FROM_DOCS": "retrieve",
        "NEEDS_ORDER_LOOKUP": "order_lookup",
        "NEEDS_TICKET": "book_ticket",
        "ESCALATE": "escalation",
    },
)
graph.add_edge("retrieve", "rag_node")
graph.add_edge("rag_node", END)
graph.add_edge("order_lookup", END)
graph.add_edge("book_ticket", END)
graph.add_edge("escalation", END)

app = graph.compile()


def _answer_text(answer) -> str:
    """Normalize Gemini content (str or list of blocks) into plain text."""
    if isinstance(answer, str):
        return answer
    if isinstance(answer, list):
        parts = []
        for block in answer:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
            else:
                parts.append(str(block))
        return "\n".join(part for part in parts if part)
    return str(answer)


if __name__ == "__main__":
    question = "I have an order to buy 2 items, I want to know the status"
    result = app.invoke({"user_question": question})

    answer = _answer_text(result["bot_answer"])
    docs = result.get("retrieve_result") or []
    route = result.get("question_type", "unknown")

    print()
    print("=" * 60)
    print("SEGNI ELECTRONICS — Support Agent")
    print("=" * 60)
    print(f"Question: {question}")
    print(f"Route:    {route}")
    print("-" * 60)
    if docs:
        print(f"Retrieved {len(docs)} chunk(s):")
        for i, doc in enumerate(docs, start=1):
            intent = (doc.metadata or {}).get("intent", "n/a")
            score = (doc.metadata or {}).get("score")
            score_text = f"{score:.3f}" if isinstance(score, (int, float)) else "n/a"
            preview = doc.page_content.replace("\n", " ")
            if len(preview) > 100:
                preview = preview[:97] + "..."
            print(f"  [{i}] intent={intent}  score={score_text}")
            print(f"      {preview}")
        print("-" * 60)
    print("Answer:")
    print(answer)
    print("=" * 60)
    print()

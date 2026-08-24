from langgraph.graph import StateGraph, START, END
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain.chat_models import init_chat_model

# from typing import list
from dotenv import load_dotenv
from pydantic import BaseModel
from app.rag import retrieve

load_dotenv()

class AgentState(BaseModel):
    user_question: str = ""
    bot_answer: str = ""
    retrieve_result: list[Document] = []

prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a customer support assistant. Answer the user question based on the contexts provided"
    ),

    (
        "human",
        """ context: {context} 
            question: {question}
        """
    )
])

llm = init_chat_model("google_genai:gemini-3.5-flash")

def retrieve_node(agent_state: AgentState):
    """ This function retrieves chunks from vector DB """
    return {"retrieve_result": retrieve(agent_state.user_question)}

def call_llm_node(agent_state: AgentState):
    """ Call LLM with retrieved chunks """
    formated_context = "\n\n".join(doc.page_content for doc in agent_state.retrieve_result)
    message = prompt.format_messages(
        context = formated_context,
        question = agent_state.user_question
    )

    llm_response = llm.invoke(message)
    
    agent_state.bot_answer = llm_response.content
    return agent_state

graph = StateGraph(AgentState)

graph.add_node("retriever", retrieve_node)
graph.add_node("call_llm", call_llm_node)

graph.add_edge(START, "retriever")
graph.add_edge("retriever", "call_llm")
graph.add_edge("call_llm", END)

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
    question = "What is your return policy?"
    result = app.invoke({"user_question": question})

    answer = _answer_text(result["bot_answer"])
    docs = result.get("retrieve_result") or []

    print()
    print("=" * 60)
    print("SEGNI ELECTRONICS — Support Agent")
    print("=" * 60)
    print(f"Question: {question}")
    print("-" * 60)
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

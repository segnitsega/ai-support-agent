from typing import Any

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from pinecone.index import Index

from app.rag.embedder import build_embedder, embed_query
from app.rag.vector_store import DEFAULT_TOP_K, query as query_vector_store


def retrieve(
    query: str,
    *,
    top_k: int = DEFAULT_TOP_K,
    namespace: str | None = None,
    metadata_filter: dict[str, Any] | None = None,
    embedder: Embeddings | None = None,
    index: Index | None = None,
) -> list[Document]:
    """Embed a user question and return the most relevant stored chunks."""
    if not query or not query.strip():
        return []

    client = embedder or build_embedder()
    vector = embed_query(query, embedder=client)
    return query_vector_store(
        vector,
        top_k=top_k,
        namespace=namespace,
        metadata_filter=metadata_filter,
        index=index,
    )

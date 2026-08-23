import hashlib
import os
from typing import Any

from dotenv import load_dotenv
from langchain_core.documents import Document
from pinecone import Pinecone
from pinecone.index import Index

load_dotenv()

DEFAULT_TOP_K = 5
DEFAULT_UPSERT_BATCH_SIZE = 100


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"{name} is not set in the environment")
    return value


def _pinecone_namespace() -> str:
    return os.getenv("PINECONE_NAMESPACE", "")


def _normalize_host(host: str) -> str:
    return host.removeprefix("https://").removeprefix("http://").rstrip("/")


def build_index() -> Index:
    """Connect to the Pinecone index configured in ``.env``."""
    pc = Pinecone(api_key=_require_env("PINECONE_API_KEY"))
    host = os.getenv("PINECONE_HOST")
    if host:
        return pc.index(host=_normalize_host(host))
    return pc.index(name=_require_env("PINECONE_INDEX_NAME"))


def _vector_id(document: Document) -> str:
    key = document.page_content + repr(sorted(document.metadata.items()))
    return hashlib.sha256(key.encode()).hexdigest()[:32]


def _sanitize_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Keep only Pinecone-compatible metadata values."""
    clean: dict[str, Any] = {}
    for key, value in metadata.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            clean[key] = value
        elif isinstance(value, list) and all(isinstance(item, str) for item in value):
            clean[key] = value
        else:
            clean[key] = str(value)
    return clean


def _to_pinecone_vectors(
    documents: list[Document],
    embeddings: list[list[float]],
    ids: list[str] | None = None,
) -> list[tuple[str, list[float], dict[str, Any]]]:
    if len(documents) != len(embeddings):
        raise ValueError(
            f"documents length ({len(documents)}) must match embeddings length ({len(embeddings)})"
        )

    expected_dim = os.getenv("EMBEDDING_DIMENSION")
    if expected_dim is not None:
        expected_dim = int(expected_dim)

    vectors: list[tuple[str, list[float], dict[str, Any]]] = []
    for index, (document, values) in enumerate(zip(documents, embeddings, strict=True)):
        if expected_dim is not None and len(values) != expected_dim:
            raise ValueError(
                f"Embedding at index {index} has dimension {len(values)}, "
                f"expected {expected_dim}"
            )
        metadata = _sanitize_metadata(document.metadata)
        metadata["text"] = document.page_content
        vector_id = ids[index] if ids is not None else _vector_id(document)
        vectors.append((vector_id, values, metadata))
    return vectors


def upsert(
    documents: list[Document],
    embeddings: list[list[float]],
    *,
    ids: list[str] | None = None,
    namespace: str | None = None,
    batch_size: int = DEFAULT_UPSERT_BATCH_SIZE,
    index: Index | None = None,
) -> int:
    """Store embedded chunks in Pinecone."""
    if not documents:
        return 0

    client = index or build_index()
    vectors = _to_pinecone_vectors(documents, embeddings, ids=ids)
    response = client.upsert(
        vectors=vectors,
        namespace=namespace if namespace is not None else _pinecone_namespace(),
        batch_size=batch_size,
    )
    return response.upserted_count or len(vectors)


def query(
    vector: list[float],
    *,
    top_k: int = DEFAULT_TOP_K,
    namespace: str | None = None,
    metadata_filter: dict[str, Any] | None = None,
    include_metadata: bool = True,
    index: Index | None = None,
) -> list[Document]:
    """Find the nearest stored chunks to a query embedding."""
    client = index or build_index()
    response = client.query(
        vector=vector,
        top_k=top_k,
        namespace=namespace if namespace is not None else _pinecone_namespace(),
        filter=metadata_filter,
        include_metadata=include_metadata,
    )

    documents: list[Document] = []
    for match in response.matches or []:
        metadata = dict(match.metadata or {})
        text = metadata.pop("text", "")
        if match.score is not None:
            metadata["score"] = match.score
        documents.append(Document(page_content=text, metadata=metadata))
    return documents

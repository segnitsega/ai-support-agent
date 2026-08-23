import os

from dotenv import load_dotenv
from langchain.embeddings import init_embeddings
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

load_dotenv()


def _embedding_model() -> str:
    model = os.getenv("EMBEDDING_MODEL")
    if not model:
        raise ValueError("EMBEDDING_MODEL is not set in the environment")
    return model


def _embedding_dimension() -> int | None:
    value = os.getenv("EMBEDDING_DIMENSION")
    if not value:
        return None
    return int(value)


def build_embedder(
    model: str | None = None,
    **kwargs,
) -> Embeddings:
    """Return a LangChain embeddings client.

    Model and optional output size come from ``EMBEDDING_MODEL`` and
    ``EMBEDDING_DIMENSION`` in ``.env``. Extra kwargs are passed through
    to the provider.
    """
    if "output_dimensionality" not in kwargs:
        dimension = _embedding_dimension()
        if dimension is not None:
            kwargs["output_dimensionality"] = dimension
    return init_embeddings(model or _embedding_model(), **kwargs)


def embed_query(
    text: str,
    *,
    embedder: Embeddings | None = None,
) -> list[float]:
    """Embed a user question for similarity search."""
    client = embedder or build_embedder()
    return client.embed_query(text)


def embed_texts(
    texts: list[str],
    *,
    embedder: Embeddings | None = None,
) -> list[list[float]]:
    """Embed many strings for indexing (one vector per string)."""
    if not texts:
        return []
    client = embedder or build_embedder()
    return client.embed_documents(texts)


def embed_documents(
    documents: list[Document],
    *,
    embedder: Embeddings | None = None,
) -> list[list[float]]:
    """Embed the ``page_content`` of chunks produced by the chunker."""
    return embed_texts(
        [doc.page_content for doc in documents],
        embedder=embedder,
    )

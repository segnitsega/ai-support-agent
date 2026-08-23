import os
import time

from dotenv import load_dotenv
from langchain.embeddings import init_embeddings
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

load_dotenv()

DEFAULT_EMBED_BATCH_SIZE = 50
DEFAULT_EMBED_BATCH_DELAY_SECONDS = 61.0
DEFAULT_EMBED_MAX_RETRIES = 5


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


def _embed_batch_size() -> int:
    return int(os.getenv("EMBEDDING_BATCH_SIZE", DEFAULT_EMBED_BATCH_SIZE))


def _embed_batch_delay_seconds() -> float:
    return float(os.getenv("EMBEDDING_BATCH_DELAY_SECONDS", DEFAULT_EMBED_BATCH_DELAY_SECONDS))


def _embed_max_retries() -> int:
    return int(os.getenv("EMBEDDING_MAX_RETRIES", DEFAULT_EMBED_MAX_RETRIES))


def _is_rate_limit_error(error: Exception) -> bool:
    message = str(error)
    return "429" in message or "RESOURCE_EXHAUSTED" in message


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
    batch_size: int | None = None,
    batch_delay_seconds: float | None = None,
    max_retries: int | None = None,
) -> list[list[float]]:
    """Embed many strings for indexing (one vector per string).

    Gemini's free tier caps embedding requests at 100/minute, so larger
    ingests are processed in batches with a pause between each batch.
    """
    if not texts:
        return []

    client = embedder or build_embedder()
    effective_batch_size = batch_size or _embed_batch_size()
    effective_delay = (
        batch_delay_seconds
        if batch_delay_seconds is not None
        else _embed_batch_delay_seconds()
    )
    effective_retries = max_retries or _embed_max_retries()

    embeddings: list[list[float]] = []
    for start in range(0, len(texts), effective_batch_size):
        if start > 0 and effective_delay > 0:
            time.sleep(effective_delay)

        batch = texts[start : start + effective_batch_size]
        for attempt in range(1, effective_retries + 1):
            try:
                batch_embeddings = client.embed_documents(
                    batch,
                    batch_size=len(batch),
                )
                break
            except Exception as error:
                if not _is_rate_limit_error(error) or attempt == effective_retries:
                    raise
                wait_seconds = effective_delay * attempt
                print(
                    f"Embedding rate limit hit; waiting {wait_seconds:.0f}s "
                    f"before retry {attempt + 1}/{effective_retries}..."
                )
                time.sleep(wait_seconds)
        embeddings.extend(batch_embeddings)
    return embeddings


def embed_documents(
    documents: list[Document],
    *,
    embedder: Embeddings | None = None,
    batch_size: int | None = None,
    batch_delay_seconds: float | None = None,
    max_retries: int | None = None,
) -> list[list[float]]:
    """Embed the ``page_content`` of chunks produced by the chunker."""
    return embed_texts(
        [doc.page_content for doc in documents],
        embedder=embedder,
        batch_size=batch_size,
        batch_delay_seconds=batch_delay_seconds,
        max_retries=max_retries,
    )

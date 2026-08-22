from typing import Any

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
SEPARATORS = ["\n\n", "\n", ". ", " ", ""]


def build_splitter(
    *,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
    separators: list[str] | None = None,
) -> RecursiveCharacterTextSplitter:
    """Return a configured recursive character splitter."""
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=separators or SEPARATORS,
        length_function=len,
        add_start_index=True,
        strip_whitespace=True,
    )


def chunk_text(
    text: str,
    metadata: dict[str, Any] | None = None,
    *,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
    separators: list[str] | None = None,
) -> list[Document]:
    """Split one string into overlapping ``Document`` chunks"""
    return chunk_texts(
        [text],
        metadatas=[metadata or {}],
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=separators,
    )


def chunk_texts(
    texts: list[str],
    metadatas: list[dict[str, Any]] | None = None,
    *,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
    separators: list[str] | None = None,
) -> list[Document]:
    """Split many strings, preserving per-text metadata on every chunk.

    Empty or whitespace-only strings are skipped.
    """
    splitter = build_splitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=separators,
    )
    source_metas = metadatas or [{}] * len(texts)
    if len(source_metas) != len(texts):
        raise ValueError(
            f"metadatas length ({len(source_metas)}) must match texts length ({len(texts)})"
        )

    documents: list[Document] = []
    for text, source_meta in zip(texts, source_metas):
        if not text or not text.strip():
            continue
        pieces = splitter.create_documents([text], metadatas=[source_meta])
        for index, piece in enumerate(pieces):
            piece.metadata["chunk_index"] = index
            piece.metadata["chunk_count"] = len(pieces)
            documents.append(piece)
    return documents

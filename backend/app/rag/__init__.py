import argparse
import json
import time
from pathlib import Path
from typing import Any

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from pinecone.index import Index

from app.rag.chunker import chunk_texts
from app.rag.embedder import build_embedder, embed_documents
from app.rag.retriever import retrieve
from app.rag.vector_store import upsert

DEFAULT_FAQ_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "faq_docs" / "support_faq.jsonl"
)

__all__ = [
    "DEFAULT_FAQ_PATH",
    "ingest",
    "load_faq_jsonl",
    "retrieve",
]


def load_faq_jsonl(path: Path | str = DEFAULT_FAQ_PATH) -> tuple[list[str], list[dict[str, Any]]]:
    """Load FAQ rows from a JSONL file."""
    faq_path = Path(path)
    if not faq_path.is_file():
        raise FileNotFoundError(f"FAQ file not found: {faq_path}")

    texts: list[str] = []
    metadatas: list[dict[str, Any]] = []
    with faq_path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            row = json.loads(stripped)
            text = row.get("text", "").strip()
            if not text:
                continue
            metadata = dict(row.get("metadata") or {})
            metadata["source_file"] = faq_path.name
            metadata["source_line"] = line_number
            texts.append(text)
            metadatas.append(metadata)
    return texts, metadatas


def ingest(
    path: Path | str = DEFAULT_FAQ_PATH,
    *,
    embedder: Embeddings | None = None,
    index: Index | None = None,
    namespace: str | None = None,
    embed_batch_size: int | None = None,
    embed_batch_delay_seconds: float | None = None,
) -> dict[str, int]:
    """Chunk, embed, and store FAQ entries from a JSONL file."""
    texts, metadatas = load_faq_jsonl(path)
    chunks = chunk_texts(texts, metadatas=metadatas)

    client = embedder or build_embedder()
    effective_batch_size = embed_batch_size or 50
    effective_delay = embed_batch_delay_seconds if embed_batch_delay_seconds is not None else 61.0
    total_upserted = 0

    for start in range(0, len(chunks), effective_batch_size):
        if start > 0 and effective_delay > 0:
            print(f"Waiting {effective_delay:.0f}s before next embedding batch...")
            time.sleep(effective_delay)

        batch_chunks = chunks[start : start + effective_batch_size]
        batch_number = start // effective_batch_size + 1
        batch_count = (len(chunks) + effective_batch_size - 1) // effective_batch_size
        print(
            f"Processing batch {batch_number}/{batch_count} "
            f"({len(batch_chunks)} chunks)..."
        )

        batch_embeddings = embed_documents(
            batch_chunks,
            embedder=client,
            batch_size=len(batch_chunks),
        )
        total_upserted += upsert(
            batch_chunks,
            batch_embeddings,
            namespace=namespace,
            index=index,
        )

    return {
        "source_rows": len(texts),
        "chunks": len(chunks),
        "upserted": total_upserted,
    }


def _print_retrieval_results(query: str, documents: list[Document]) -> None:
    print(f'Query: "{query}"')
    if not documents:
        print("No matches found.")
        return
    for rank, document in enumerate(documents, start=1):
        score = document.metadata.get("score")
        intent = document.metadata.get("intent")
        score_text = f"{score:.4f}" if isinstance(score, (int, float)) else "n/a"
        print(f"\n[{rank}] score={score_text} intent={intent}")
        print(document.page_content)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Segni Electronics RAG pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser(
        "ingest",
        help="Chunk, embed, and upsert support_faq.jsonl into Pinecone",
    )
    ingest_parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_FAQ_PATH,
        help=f"Path to FAQ JSONL (default: {DEFAULT_FAQ_PATH})",
    )
    ingest_parser.add_argument(
        "--embed-batch-size",
        type=int,
        default=50,
        help="Chunks to embed per Gemini batch (default: 50)",
    )
    ingest_parser.add_argument(
        "--embed-batch-delay",
        type=float,
        default=61.0,
        help="Seconds to wait between embedding batches (default: 61)",
    )

    retrieve_parser = subparsers.add_parser(
        "retrieve",
        help="Search Pinecone for chunks relevant to a question",
    )
    retrieve_parser.add_argument("query", help="User question to search for")
    retrieve_parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of chunks to return (default: 5)",
    )

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "ingest":
        stats = ingest(
            args.input,
            embed_batch_size=args.embed_batch_size,
            embed_batch_delay_seconds=args.embed_batch_delay,
        )
        print(
            "Ingest complete: "
            f"{stats['source_rows']} FAQ rows -> "
            f"{stats['chunks']} chunks -> "
            f"{stats['upserted']} vectors upserted"
        )
        return

    if args.command == "retrieve":
        results = retrieve(args.query, top_k=args.top_k)
        _print_retrieval_results(args.query, results)


if __name__ == "__main__":
    main()

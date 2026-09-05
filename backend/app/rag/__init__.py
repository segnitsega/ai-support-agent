import argparse
import json
import re
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
    Path(__file__).resolve().parents[2]
    / "data"
    / "faq_docs"
    / "segni_support_handbook.md"
)

_SECTION_HEADER = re.compile(r"^##\s+(.+)$", re.MULTILINE)

__all__ = [
    "DEFAULT_FAQ_PATH",
    "ingest",
    "load_faq_jsonl",
    "load_markdown",
    "load_support_docs",
    "retrieve",
]


def load_faq_jsonl(path: Path | str) -> tuple[list[str], list[dict[str, Any]]]:
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
            metadata["source_format"] = "jsonl"
            texts.append(text)
            metadatas.append(metadata)
    return texts, metadatas


def load_markdown(path: Path | str) -> tuple[list[str], list[dict[str, Any]]]:
    """Load a support handbook markdown file as section-sized documents.

    Splits on ``##`` headings so each policy section is embedded as its own
    unit (then further chunked if still long).
    """
    md_path = Path(path)
    if not md_path.is_file():
        raise FileNotFoundError(f"Markdown file not found: {md_path}")

    content = md_path.read_text(encoding="utf-8").strip()
    if not content:
        return [], []

    matches = list(_SECTION_HEADER.finditer(content))
    texts: list[str] = []
    metadatas: list[dict[str, Any]] = []

    if not matches:
        texts.append(content)
        metadatas.append(
            {
                "source_file": md_path.name,
                "source_format": "markdown",
                "title": md_path.stem,
                "section": "full_document",
            }
        )
        return texts, metadatas

    # Keep a short preamble (title / intro before the first ##) if present.
    preamble = content[: matches[0].start()].strip()
    if preamble:
        texts.append(preamble)
        metadatas.append(
            {
                "source_file": md_path.name,
                "source_format": "markdown",
                "title": "Introduction",
                "section": "preamble",
                "category": "GENERAL",
            }
        )

    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        section_text = content[start:end].strip()
        if not section_text:
            continue
        heading = match.group(1).strip()
        texts.append(section_text)
        metadatas.append(
            {
                "source_file": md_path.name,
                "source_format": "markdown",
                "title": heading,
                "section": heading,
                "category": _category_from_heading(heading),
                "section_index": index,
            }
        )

    return texts, metadatas


def load_support_docs(path: Path | str) -> tuple[list[str], list[dict[str, Any]]]:
    """Load support docs from ``.md`` or ``.jsonl`` based on file suffix."""
    doc_path = Path(path)
    suffix = doc_path.suffix.lower()
    if suffix in {".md", ".markdown"}:
        return load_markdown(doc_path)
    if suffix == ".jsonl":
        return load_faq_jsonl(doc_path)
    raise ValueError(
        f"Unsupported support-doc format {suffix!r}. Use .md or .jsonl ({doc_path})"
    )


def _category_from_heading(heading: str) -> str:
    lowered = heading.lower()
    if "return" in lowered or "refund" in lowered:
        return "RETURNS"
    if re.search(r"\border", lowered):
        return "ORDER"
    if "ship" in lowered or "delivery" in lowered:
        return "SHIPPING"
    if "payment" in lowered or "invoice" in lowered:
        return "PAYMENT"
    if "warranty" in lowered or "defective" in lowered:
        return "WARRANTY"
    if "account" in lowered or "password" in lowered or "security" in lowered:
        return "ACCOUNT"
    if "contact" in lowered or "support" in lowered or "escalat" in lowered:
        return "SUPPORT"
    if "review" in lowered or "newsletter" in lowered:
        return "ACCOUNT"
    if "quick answer" in lowered:
        return "GENERAL"
    return "GENERAL"


def ingest(
    path: Path | str = DEFAULT_FAQ_PATH,
    *,
    embedder: Embeddings | None = None,
    index: Index | None = None,
    namespace: str | None = None,
    embed_batch_size: int | None = None,
    embed_batch_delay_seconds: float | None = None,
) -> dict[str, int]:
    """Chunk, embed, and store support docs from a Markdown or JSONL file."""
    texts, metadatas = load_support_docs(path)
    chunks = chunk_texts(texts, metadatas=metadatas)

    client = embedder or build_embedder()
    effective_batch_size = embed_batch_size or 50
    effective_delay = (
        embed_batch_delay_seconds if embed_batch_delay_seconds is not None else 61.0
    )
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
        title = document.metadata.get("title") or document.metadata.get("intent")
        score_text = f"{score:.4f}" if isinstance(score, (int, float)) else "n/a"
        print(f"\n[{rank}] score={score_text} title={title}")
        print(document.page_content)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Segni Electronics RAG pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser(
        "ingest",
        help="Chunk, embed, and upsert a support .md or .jsonl file into Pinecone",
    )
    ingest_parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_FAQ_PATH,
        help=f"Path to support docs (default: {DEFAULT_FAQ_PATH})",
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
            f"{stats['source_rows']} source section(s) -> "
            f"{stats['chunks']} chunks -> "
            f"{stats['upserted']} vectors upserted"
        )
        return

    if args.command == "retrieve":
        results = retrieve(args.query, top_k=args.top_k)
        _print_retrieval_results(args.query, results)


if __name__ == "__main__":
    main()

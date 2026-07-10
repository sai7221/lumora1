"""
File text extraction + chunking for the RAG pipeline.

Flow: raw file bytes -> plain text -> overlapping word-based chunks
-> (in the router) each chunk gets embedded and stored.
"""
import io
from pypdf import PdfReader
from docx import Document as DocxDocument

MAX_FILE_SIZE_BYTES = 8 * 1024 * 1024  # 8 MB — generous for text notes, keeps embedding calls bounded


def extract_text(file_bytes: bytes, file_type: str) -> str:
    if file_type == "pdf":
        reader = PdfReader(io.BytesIO(file_bytes))
        pages_text = [page.extract_text() or "" for page in reader.pages]
        return "\n\n".join(pages_text)

    if file_type == "docx":
        doc = DocxDocument(io.BytesIO(file_bytes))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())

    if file_type == "txt":
        return file_bytes.decode("utf-8", errors="ignore")

    raise ValueError(f"Unsupported file type: {file_type}")


def chunk_text(text: str, chunk_size_words: int = 350, overlap_words: int = 50) -> list[str]:
    """
    Word-based sliding window chunking. ~350 words (~450-500 tokens) per
    chunk with 50-word overlap so context isn't lost at chunk boundaries.
    """
    words = text.split()
    if not words:
        return []

    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size_words
        chunk_words = words[start:end]
        chunk = " ".join(chunk_words).strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(words):
            break
        start = end - overlap_words

    return chunks


def format_embedding_for_pg(embedding: list[float]) -> str:
    """
    pgvector's text input format is '[v1,v2,v3,...]'. Sending this exact
    string through PostgREST lets Postgres cast it straight to `vector`
    — sending a raw JSON array instead gets serialized as a Postgres
    array literal ('{v1,v2}') which the vector type won't accept.
    """
    return "[" + ",".join(f"{v:.8f}" for v in embedding) + "]"

"""Chinese-optimized text chunking strategy."""

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document


# Chinese-prioritized separators: paragraph → sentence → phrase → word
_CHINESE_SEPARATORS = [
    "\n\n",     # Double newline (paragraph)
    "\n",       # Single newline
    "。",       # Chinese period
    "！",       # Chinese exclamation
    "？",       # Chinese question mark
    "；",       # Chinese semicolon
    "，",       # Chinese comma
    ".",        # English period
    "!",        # English exclamation
    "?",        # English question mark
    " ",        # Space (last resort)
]


def create_splitter(
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> RecursiveCharacterTextSplitter:
    """Create a Chinese-optimized recursive text splitter.

    chunk_size=500 chars ≈ 300 tokens for Chinese text.
    chunk_overlap=50 chars (10%) for context continuity.
    """
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=_CHINESE_SEPARATORS,
        length_function=len,
        is_separator_regex=False,
    )


def split_documents(
    documents: list[Document],
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> list[Document]:
    """Split a list of documents into chunks."""
    splitter = create_splitter(chunk_size, chunk_overlap)
    return splitter.split_documents(documents)

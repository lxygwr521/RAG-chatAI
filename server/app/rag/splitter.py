"""Chinese-optimized text chunking strategy."""

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document


# Chinese-prioritized separators: paragraph → section → sentence → phrase → word
# "【" targets health-document section markers like 【核心原则】, keeping each
# section's heading and body together instead of splitting them across chunks.
_CHINESE_SEPARATORS = [
    "\n\n",     # Double newline (paragraph)
    "【",       # Chinese bracket section marker (health docs)
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
    chunk_size: int = 800,
    chunk_overlap: int = 120,
) -> RecursiveCharacterTextSplitter:
    """Create a Chinese-optimized recursive text splitter.

    chunk_size=800 chars 覆盖一个完整的中文健康知识条目
    (通常 400-700 字)，避免句子被截断。
    chunk_overlap=120 chars (15%) 确保跨 chunk 的语义连贯性。
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
    chunk_size: int = 600,
    chunk_overlap: int = 80,
) -> list[Document]:
    """Split a list of documents into chunks."""
    splitter = create_splitter(chunk_size, chunk_overlap)
    return splitter.split_documents(documents)

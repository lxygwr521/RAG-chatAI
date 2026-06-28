"""Document loaders for knowledge base ingestion.

Supports: txt, md, pdf, csv, json, log, xml, yml, yaml
"""

import os
from pathlib import Path

from langchain_community.document_loaders import (
    TextLoader,
    PyPDFLoader,
    CSVLoader,
    JSONLoader,
)
from langchain_core.documents import Document


def _detect_loader(file_path: str) -> str:
    """Pick the right LangChain loader based on file extension."""
    ext = Path(file_path).suffix.lower()
    return ext


async def load_document(file_path: str) -> list[Document]:
    """Load a single document into LangChain Document objects.

    Returns a list of Document(page_content=..., metadata={source: ...}).
    """
    ext = _detect_loader(file_path)

    if ext == ".pdf":
        loader = PyPDFLoader(file_path)
    elif ext == ".csv":
        loader = CSVLoader(file_path)
    elif ext == ".json":
        loader = JSONLoader(file_path, jq_schema=".", text_content=False)
    else:
        # txt, md, log, xml, yml, yaml, ini, conf — all plain text
        loader = TextLoader(file_path, encoding="utf-8")

    docs = loader.load()

    # Normalize metadata: add filename as source
    filename = os.path.basename(file_path)
    for doc in docs:
        doc.metadata["source"] = filename
        doc.metadata["file_path"] = file_path

    return docs

"""Lightweight tokenization helpers for lexical retrieval."""

from __future__ import annotations

import re

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[._:/-][a-z0-9]+)*|[\u4e00-\u9fff]+", re.IGNORECASE)
_ALNUM_RE = re.compile(r"[a-z]+|\d+")


def tokenize(text: str) -> list[str]:
    """Tokenize mixed Chinese/English health text for BM25-style matching.

    Chinese spans are represented as unigrams plus bigrams. English and numeric
    spans are lower-cased, with split sub-parts retained for units like mmol/L.
    """
    if not text:
        return []

    tokens: list[str] = []
    for match in _TOKEN_RE.finditer(text.lower()):
        token = match.group(0)
        if _is_cjk_span(token):
            tokens.extend(token)
            tokens.extend(token[i : i + 2] for i in range(len(token) - 1))
            if len(token) <= 8:
                tokens.append(token)
            continue

        tokens.append(token)
        for part in _ALNUM_RE.findall(token):
            if part != token:
                tokens.append(part)

    return tokens


def _is_cjk_span(value: str) -> bool:
    return all("\u4e00" <= ch <= "\u9fff" for ch in value)

from __future__ import annotations

import pickle
import re
from pathlib import Path


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9][a-z0-9+\-.#]*", text.lower())


def build_bm25(texts: list[str]):
    from rank_bm25 import BM25Okapi

    tokenized = [tokenize(text) for text in texts]
    return BM25Okapi(tokenized), tokenized


def save_pickle(obj: object, path: Path) -> None:
    with open(path, "wb") as f:
        pickle.dump(obj, f, protocol=pickle.HIGHEST_PROTOCOL)


def load_pickle(path: Path):
    with open(path, "rb") as f:
        return pickle.load(f)


def save_faiss(index, path: Path) -> None:
    import faiss

    faiss.write_index(index, str(path))


def load_faiss(path: Path):
    import faiss

    return faiss.read_index(str(path))

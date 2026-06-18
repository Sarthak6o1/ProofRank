from __future__ import annotations

from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_CACHE = str(ROOT / "models")


class Embedder:
    def __init__(self, model_name: str = DEFAULT_MODEL, cache_dir: str | None = DEFAULT_CACHE) -> None:
        from sentence_transformers import SentenceTransformer

        kwargs: dict = {}
        if cache_dir:
            Path(cache_dir).mkdir(parents=True, exist_ok=True)
            kwargs["cache_folder"] = cache_dir
        self.model_name = model_name
        self.model = SentenceTransformer(model_name, **kwargs)

    def encode(self, texts: list[str], batch_size: int = 128) -> np.ndarray:
        return self.model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=True,
        ).astype("float32")

    def encode_one(self, text: str) -> np.ndarray:
        return self.encode([text], batch_size=1)[0]

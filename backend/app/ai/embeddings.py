"""Text similarity for duplicate detection.

Uses TF-IDF vectors (word + character n-grams) fitted ONCE over the bundled
complaints corpus so IDF statistics are meaningful, then compares pairs with
cosine similarity. Robust to wording differences ("huge pothole" vs "large
hole"), works for English and romanized Hindi, fully offline.
"""
import re
from functools import lru_cache

_token_re = re.compile(r"[^\w]+", re.UNICODE)


def normalize(text: str) -> str:
    return _token_re.sub(" ", (text or "").lower()).strip()


@lru_cache(maxsize=2)
def _vectorizer(kind: str):
    """Fit on the bundled complaints corpus for stable IDF statistics."""
    from sklearn.feature_extraction.text import TfidfVectorizer

    from app.ai.text_classifier import _load_dataset

    texts, _ = _load_dataset()
    if kind == "word":
        vec = TfidfVectorizer(lowercase=True, ngram_range=(1, 2), sublinear_tf=True, min_df=1)
    else:
        vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), sublinear_tf=True, min_df=2)
    vec.fit(texts)
    return vec


@lru_cache(maxsize=None)
def _cached_norm(text: str) -> str:
    return normalize(text)


def similarity(a: str, b: str) -> float:
    """Blended cosine similarity in [0,1]; 0 when either side is empty."""
    a_n, b_n = _cached_norm(a or ""), _cached_norm(b or "")
    if not a_n or not b_n:
        return 0.0
    try:
        import numpy as np

        scores = []
        for kind in ("word", "char"):
            vec = _vectorizer(kind)
            m = vec.transform([a_n, b_n])
            va, vb = m[0].toarray()[0], m[1].toarray()[0]
            denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
            scores.append(0.0 if denom == 0 else float(np.dot(va, vb) / denom))
        return max(0.0, min(1.0, 0.5 * scores[0] + 0.5 * scores[1]))
    except Exception:
        return _jaccard_fallback(a_n, b_n)


def _jaccard_fallback(a: str, b: str) -> float:
    sa, sb = set(a.split()), set(b.split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)

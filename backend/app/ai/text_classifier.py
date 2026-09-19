"""Text complaint classifier: TF-IDF + LogisticRegression (fully offline).

Trained on app/ai/dataset/complaints.csv at first use and cached to disk with
joblib. Records provider/model/version so administrators can audit every
prediction. If scikit-learn or the dataset is unavailable, callers must
degrade gracefully (see services/pipeline.py).
"""
import csv
import hashlib
from functools import lru_cache
from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("sahayata.ai.classifier")

DATASET_PATH = Path(__file__).parent / "dataset" / "complaints.csv"
MODEL_DIR = Path(settings.UPLOAD_DIR).parent / "models"

MODEL_NAME = "tfidf-logreg"
MODEL_VERSION = "1.0.0"


def _load_dataset() -> tuple[list[str], list[str]]:
    texts, labels = [], []
    with DATASET_PATH.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            text = (row.get("text") or "").strip()
            label = (row.get("label") or "").strip()
            if text and label:
                texts.append(text)
                labels.append(label)
    return texts, labels


def _model_cache_path(digest: str) -> Path:
    return MODEL_DIR / f"text_clf_{digest}.joblib"


@lru_cache(maxsize=1)
def _get_pipeline():
    """Train (or load cached) pipeline. Raises on failure so caller can degrade."""
    from joblib import dump, load
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline

    texts, labels = _load_dataset()
    if not texts:
        raise RuntimeError("classifier dataset is empty")

    digest = hashlib.sha1(("|".join(labels) + "#" + str(len(texts))).encode()).hexdigest()[:12]
    cache = _model_cache_path(digest)
    if cache.exists():
        try:
            return load(cache), digest
        except Exception:
            log.warning("cached model unreadable; retraining", exc_info=True)

    pipe = Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    lowercase=True,
                    ngram_range=(1, 2),
                    sublinear_tf=True,
                    min_df=1,
                    stop_words=None,  # keep Hinglish + domain words
                ),
            ),
            (
                "clf",
                LogisticRegression(max_iter=2000, C=6.0, class_weight="balanced"),
            ),
        ]
    )
    pipe.fit(texts, labels)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    try:
        dump(pipe, cache)
    except Exception:
        log.warning("could not cache trained model", exc_info=True)
    return pipe, digest


def available() -> bool:
    try:
        _get_pipeline()
        return True
    except Exception:
        return False


def classify(text: str) -> dict | None:
    """Return {category_slug, confidence, keywords, top3} or None on failure."""
    clean = " ".join((text or "").split())
    if not clean:
        return None
    try:
        import numpy as np

        pipe, digest = _get_pipeline()
        proba = pipe.predict_proba([clean])[0]
        classes = pipe.classes_
        order = np.argsort(proba)[::-1]
        top3 = [{"category": classes[i], "confidence": round(float(proba[i]), 4)} for i in order[:3]]

        # Keywords: highest-weight tf-idf tokens of this input.
        vec = pipe.named_steps["tfidf"]
        clf = pipe.named_steps["clf"]
        row = vec.transform([clean])
        weights = row.toarray()[0]
        vocab = np.array(vec.get_feature_names_out())
        top_idx = weights.argsort()[::-1][:8]
        # Prefer tokens that push towards the winning class.
        win = order[0]
        coefs = clf.coef_[win]
        scored = []
        for i in top_idx:
            if weights[i] <= 0:
                continue
            token = vocab[i]
            score = float(weights[i] * max(coef_pos, 0)) if (coef_pos := float(coefs[i])) else 0.0
            scored.append(token)
        keywords = scored[:5]

        return {
            "category_slug": classes[order[0]],
            "confidence": round(float(proba[order[0]]), 4),
            "keywords": keywords,
            "top3": top3,
            "model_version": MODEL_VERSION,
            "model_name": f"{MODEL_NAME}:{digest}",
        }
    except Exception:
        log.exception("classification failed")
        return None

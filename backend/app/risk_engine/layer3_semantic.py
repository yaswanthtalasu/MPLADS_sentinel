"""
Layer 3 - Semantic Intelligence
===============================

Turns `work_description` + `activity_name` into vectors and finds each work's
nearest neighbours.

Why the obvious approach fails here
-----------------------------------
MPLADS descriptions are template-driven:

    "Construction of MID DAY Meal Shed in Govt Primary school Bajakhana"
    "Construction of mid-day meal Shed in Govt Primary school Dana Romana"

These are two *different* schools. A dimensionality-reduced embedding scores
them at 0.99 similarity, because the reduction throws away exactly the rare
tokens - the village names - that tell them apart. Doing that flags 98% of
the portfolio as duplicates, which is the same as flagging nothing.

So the tfidf backend keeps the full sparse matrix with min_df=1: rare village
and landmark tokens carry high IDF weight and become the discriminator.
The resulting separation is clean:

    ~1.00   byte-identical description        -> real duplicate
    ~0.87   same template, different village  -> not a duplicate
    ~0.73   same activity type, different site-> not a duplicate

A duplicate is also only interesting in context. The same water tanker
purchased in two different states is procurement, not duplication; the same
work recommended twice under one implementing agency is a lead. The score
below weights same-agency duplicates far more heavily than global ones.

Backends
--------
tfidf (default)  word 1-2 grams, min_df=1, full sparse cosine. Offline,
                 deterministic, ~1 minute for 34k rows.
sbert (opt-in)   sentence-transformers all-MiniLM-L6-v2. Set
                 MPLADS_EMBEDDING_BACKEND=sbert before running the build.
                 Note that dense embeddings compress similarity upward, so
                 config.NEAR_DUPLICATE_THRESHOLD should be re-calibrated
                 before reading anything into an sbert run.
"""

from __future__ import annotations

import os

import numpy as np
import pandas as pd
import scipy.sparse as sp
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

from . import config
from .scoring import score_0_100


# ---------------------------------------------------------------------------
# embedding backends
# ---------------------------------------------------------------------------
def _embed_tfidf(texts: list[str]):
    vec = TfidfVectorizer(
        ngram_range=(1, 2),
        min_df=1,              # keep rare village names - they are the signal
        sublinear_tf=True,
        strip_accents="unicode",
        dtype=np.float32,
    )
    return normalize(vec.fit_transform(texts))


def _embed_sbert(texts: list[str]) -> np.ndarray:
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(config.SBERT_MODEL_NAME)
    return model.encode(
        texts,
        batch_size=256,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,
    ).astype(np.float32)


def embed(texts: list[str]):
    backend = os.environ.get(config.SEMANTIC_BACKEND_ENV, "tfidf").lower()
    if backend == "sbert":
        try:
            return _embed_sbert(texts), "sbert:" + config.SBERT_MODEL_NAME
        except Exception as exc:  # noqa: BLE001
            print(f"  [layer3] sbert unavailable ({exc}); falling back to tfidf")
    return _embed_tfidf(texts), "tfidf-sparse(1,2)min_df=1"


# ---------------------------------------------------------------------------
# neighbour search
# ---------------------------------------------------------------------------
def _chunked_topk(emb, k: int, chunk: int = 1024):
    """
    Exact top-k cosine neighbours without materialising the full 34k x 34k
    similarity matrix. Peak extra memory is chunk x n floats (~140 MB at
    chunk=1024), so the build stays runnable on a modest laptop.
    Works with either a sparse TF-IDF matrix or a dense embedding array.
    """
    n = emb.shape[0]
    kk = k - 1
    top_sim = np.zeros((n, kk), dtype=np.float32)
    top_idx = np.zeros((n, kk), dtype=np.int32)
    is_sparse = sp.issparse(emb)

    for start in range(0, n, chunk):
        stop = min(start + chunk, n)
        block = emb[start:stop] @ emb.T
        block = block.toarray() if is_sparse else np.asarray(block)
        rows = np.arange(stop - start)
        block[rows, np.arange(start, stop)] = -1.0          # drop self-match
        part = np.argpartition(-block, kth=kk - 1, axis=1)[:, :kk]
        vals = block[rows[:, None], part]
        order = np.argsort(-vals, axis=1)
        top_idx[start:stop] = part[rows[:, None], order]
        top_sim[start:stop] = vals[rows[:, None], order]
        del block
    return top_sim, top_idx


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def run(df: pd.DataFrame):
    """
    Returns
    -------
    signals   : per-project semantic scores, indexed like df
    neighbours: long-form table of top-k neighbours (for the UI and Layer 4)
    emb       : the embedding matrix
    backend   : name of the backend actually used
    """
    texts = df["semantic_text"].fillna("").astype(str).tolist()
    emb, backend = embed(texts)
    print(f"  [layer3] backend={backend} shape={emb.shape}")

    k = min(config.SEMANTIC_NEIGHBOURS + 1, len(df))
    sim_n, idx_n = _chunked_topk(emb, k)

    codes = df["work_code"].to_numpy()
    ida = df["ida"].fillna("").to_numpy()
    const = df["constituency"].fillna("").to_numpy()
    activity = df["activity_name"].fillna("").to_numpy()

    rows = []
    for i in range(len(df)):
        for rank, (j, s) in enumerate(zip(idx_n[i], sim_n[i]), start=1):
            if s < 0.35:
                continue
            rows.append((
                codes[i], codes[j], float(round(s, 4)), rank,
                int(ida[i] == ida[j]),
                int(const[i] == const[j]),
                int(activity[i] == activity[j]),
            ))
    neighbours = pd.DataFrame(rows, columns=[
        "work_code", "similar_work_code", "similarity", "rank",
        "same_ida", "same_constituency", "same_activity",
    ])

    near = sim_n >= config.NEAR_DUPLICATE_THRESHOLD
    same_ida_matrix = ida[idx_n] == ida[:, None]
    same_const_matrix = const[idx_n] == const[:, None]

    max_sim = pd.Series(sim_n.max(axis=1), index=df.index)
    n_near = pd.Series(near.sum(axis=1), index=df.index)
    n_near_ida = pd.Series((near & same_ida_matrix).sum(axis=1), index=df.index)
    n_near_const = pd.Series((near & same_const_matrix).sum(axis=1), index=df.index)

    signals = pd.DataFrame(index=df.index)
    signals["semantic_max_similarity"] = max_sim.round(4)
    signals["semantic_near_duplicate_count"] = n_near
    signals["semantic_near_duplicate_same_ida"] = n_near_ida
    signals["semantic_near_duplicate_same_constituency"] = n_near_const
    # A duplicate is only reportable when it sits inside the same agency or
    # the same constituency - identical text in two different states is a
    # shared procurement template, not a red flag.
    signals["is_near_duplicate"] = (
        (max_sim >= config.NEAR_DUPLICATE_THRESHOLD) & ((n_near_ida + n_near_const) > 0)
    ).astype(int)
    signals["is_strong_duplicate"] = (
        (max_sim >= config.STRONG_DUPLICATE_THRESHOLD) & (n_near_ida > 0)
    ).astype(int)

    raw = (
        0.25 * max_sim.clip(lower=0) ** 4
        + 0.10 * n_near.clip(upper=5)
        + 0.50 * n_near_ida.clip(upper=5)
        + 0.30 * n_near_const.clip(upper=5)
    )
    signals["semantic_similarity_raw"] = raw.round(4)
    signals["semantic_similarity"] = score_0_100(raw)
    return signals, neighbours, emb, backend

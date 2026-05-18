#!/usr/bin/env python3
"""
Precompute embedding visualization data for the dashboard server.

Loads embeddings from ChromaDB, runs dimensionality reduction once,
and saves coordinates, metadata, and timeline frames as JSON files.

Run once after embedding or when you want to refresh visualizations:
    python dashboard/scripts/precompute_embedding_viz.py
    python dashboard/scripts/precompute_embedding_viz.py --force

Output:
    dashboard/data/embedding_coords_2d.json   — 2D UMAP coordinates
    dashboard/data/embedding_coords_3d.json   — 3D UMAP coordinates (optional)
    dashboard/data/embedding_metadata.json    — chunk metadata
    dashboard/data/embedding_timeline.json    — pre-bucketed timeline frames
    dashboard/data/umap_2d_reducer.pkl        — cached reducer (for search)
"""

import argparse
import json
import pickle
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

from personaldb.store import Store


def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def load_chroma_data(store: Store):
    """Load embeddings + metadata from ChromaDB via Store."""
    import chromadb

    client = store.get_chroma_client()
    collection = store.get_chroma_collection()

    total = collection.count()
    batch_size = 500
    all_embs = []
    all_docs = []
    all_metas = []

    for offset in range(0, total, batch_size):
        limit = min(batch_size, total - offset)
        result = collection.get(
            include=["embeddings", "documents", "metadatas"],
            limit=limit,
            offset=offset,
        )
        all_embs.extend(result["embeddings"])
        all_docs.extend(result.get("documents") or [""] * limit)
        all_metas.extend(result.get("metadatas") or [{}] * limit)

    emb_array = np.array(all_embs, dtype=np.float32)

    metadata = []
    for i in range(len(emb_array)):
        meta = all_metas[i] if i < len(all_metas) else {}
        ts = meta.get("timestamp_ms")
        entry = {
            "id": i,
            "content": all_docs[i][:300] if i < len(all_docs) else "",
            "sender_name": meta.get("sender_name", meta.get("sender", "")),
            "timestamp_ms": ts,
            "conversation_id": meta.get("conversation_id", ""),
            "topic_label": meta.get("topic_label", ""),
            "chunk_id": meta.get("chunk_id", str(i)),
        }
        if ts:
            try:
                entry["timestamp_iso"] = datetime.fromtimestamp(ts / 1000).isoformat()
            except (OSError, ValueError, OverflowError):
                pass
        metadata.append(entry)

    log(f"Loaded {len(emb_array)} embeddings from ChromaDB ({total} total)")
    return emb_array, metadata


def reduce_embeddings(
    embeddings: np.ndarray,
    method: str = "umap",
    n_components: int = 2,
    force_refit: bool = False,
    store: Store = None,
) -> Tuple[List[Dict[str, Any]], Any]:
    """Reduce embeddings. Returns (coords_list, reducer_object)."""
    n = len(embeddings)

    if n < 15 and method in ("umap", "tsne"):
        log(f"Only {n} points — falling back to PCA")
        method = "pca"

    reducer_path = store.dashboard_data_dir / f"{method}_{n_components}d_reducer.pkl"

    if reducer_path.exists() and not force_refit:
        log(f"Loading cached {method} reducer from {reducer_path}")
        with open(reducer_path, "rb") as f:
            reducer = pickle.load(f)
        coords_2d = np.array(reducer.transform(embeddings))
    elif method == "umap":
        log(f"Fitting UMAP {n_components}D on {n} points...")
        import umap
        reducer = umap.UMAP(
            n_neighbors=15, min_dist=0.1, n_components=n_components,
            metric="cosine", random_state=42,
        )
        coords_2d = reducer.fit_transform(embeddings)
        reducer_path.parent.mkdir(parents=True, exist_ok=True)
        with open(reducer_path, "wb") as f:
            pickle.dump(reducer, f)
    elif method == "tsne":
        log(f"Fitting t-SNE {n_components}D on {n} points (slower)...")
        from sklearn.manifold import TSNE
        reducer = TSNE(
            n_components=n_components, perplexity=min(30, n - 1),
            random_state=42, n_jobs=-1,
        )
        coords_2d = reducer.fit_transform(embeddings)
        reducer_path.parent.mkdir(parents=True, exist_ok=True)
        with open(reducer_path, "wb") as f:
            pickle.dump(reducer, f)
    else:  # pca
        log(f"Running PCA {n_components}D on {n} points")
        from sklearn.decomposition import PCA
        reducer = PCA(n_components=n_components, random_state=42)
        coords_2d = reducer.fit_transform(embeddings)
        reducer_path.parent.mkdir(parents=True, exist_ok=True)
        with open(reducer_path, "wb") as f:
            pickle.dump(reducer, f)

    coords_list = []
    for i in range(len(coords_2d)):
        pt = {
            "x": float(coords_2d[i, 0]),
            "y": float(coords_2d[i, 1]),
            "id": i,
        }
        if n_components >= 3:
            pt["z"] = float(coords_2d[i, 2])
        coords_list.append(pt)

    log(f"Reduced to {n_components}D via {method}: {len(coords_list)} points")
    return coords_list, reducer


def build_timeline_frames(
    coords: List[Dict[str, Any]],
    metadata: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Pre-bucket coordinates into monthly frames for timeline animation."""
    valid = []
    for i, c in enumerate(coords):
        meta = metadata[i] if i < len(metadata) else {}
        ts = meta.get("timestamp_ms")
        if ts:
            valid.append((c, meta, ts))

    if not valid:
        return []

    buckets: Dict[str, List[int]] = defaultdict(list)
    for c, meta, ts in valid:
        dt = datetime.fromtimestamp(ts / 1000)
        label = dt.strftime("%Y-%m")
        buckets[label].append(c["id"])

    frames = []
    for label in sorted(buckets.keys()):
        frame_indices = buckets[label]
        frame_coords = []
        for idx in frame_indices:
            if idx < len(coords):
                pt = coords[idx]
                frame_meta = metadata[idx] if idx < len(metadata) else {}
                frame_coords.append({
                    "x": pt["x"],
                    "y": pt["y"],
                    "id": pt["id"],
                    "text": frame_meta.get("content", "")[:100],
                    "sender": frame_meta.get("sender_name", ""),
                })
        frames.append({"time_label": label, "coords": frame_coords})

    return frames


def main():
    parser = argparse.ArgumentParser(description="Precompute embedding visualization data")
    parser.add_argument("--force", action="store_true", help="Force refit of UMAP reducer")
    parser.add_argument("--method", default="umap", choices=["umap", "tsne", "pca"])
    parser.add_argument("--dim", type=int, default=2, choices=[2, 3])
    args = parser.parse_args()

    store = Store()
    start = time.time()

    # 1. Load from ChromaDB
    log("Loading embeddings from ChromaDB...")
    emb_array, metadata = load_chroma_data(store)

    if len(emb_array) == 0:
        log("Error: No embeddings found in ChromaDB. Run 'personalb embed' first.")
        sys.exit(1)

    # 2. Reduce
    log(f"Reducing {len(emb_array)} embeddings to {args.dim}D via {args.method}...")
    coords, reducer = reduce_embeddings(
        emb_array, method=args.method, n_components=args.dim,
        force_refit=args.force, store=store,
    )

    # 3. Merge coordinates with metadata for the full payload
    for i, pt in enumerate(coords):
        if i < len(metadata):
            pt.update({
                "text": metadata[i].get("content", "")[:200],
                "sender": metadata[i].get("sender_name", ""),
                "timestamp": metadata[i].get("timestamp_ms"),
                "conversation_id": metadata[i].get("conversation_id", ""),
                "topic": metadata[i].get("topic_label", ""),
            })

    # 4. Save coordinates JSON
    coords_path = store.dashboard_data_dir / f"embedding_coords_{args.dim}d.json"
    store.dashboard_data_dir.mkdir(parents=True, exist_ok=True)
    with open(coords_path, "w", encoding="utf-8") as f:
        json.dump(coords, f, ensure_ascii=False)
    log(f"Saved {len(coords)} coordinate points to {coords_path}")

    # 5. Save metadata JSON
    meta_path = store.dashboard_data_dir / "embedding_metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False)
    log(f"Saved metadata to {meta_path}")

    # 6. Build and save timeline frames
    log("Building timeline frames...")
    frames = build_timeline_frames(coords, metadata)
    timeline_path = store.dashboard_data_dir / "embedding_timeline.json"
    with open(timeline_path, "w", encoding="utf-8") as f:
        json.dump({"frames": frames}, f, ensure_ascii=False)
    log(f"Saved {len(frames)} timeline frames to {timeline_path}")

    elapsed = time.time() - start
    log(f"Precompute complete in {elapsed:.1f}s. Dashboard server ready for instant viz.")


if __name__ == "__main__":
    main()

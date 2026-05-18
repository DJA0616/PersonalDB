#!/usr/bin/env python3
"""
Embedding visualization for PersonalDB dashboard.
Projects ChromaDB embeddings into 2D/3D using UMAP/t-SNE/PCA,
generates Plotly interactive views.

CLI mode:
    python generate_embedding_viz.py --chroma-path data/chroma --input data/processed/messages.jsonl
    python generate_embedding_viz.py --query "how are you doing"

API mode (imported by server.py):
    from generate_embedding_viz import load_chroma_embeddings, reduce_embeddings, search_similar, build_timeline_frames
"""
import argparse
import json
import pickle
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import plotly.graph_objects as go
import plotly.io as pio
import requests
from sklearn.decomposition import PCA

# ── Constants (defaults — overridden from config in main(), or via Store) ──
OLLAMA_API_URL = "http://localhost:11434/api"
EMBEDDING_MODEL = "nomic-embed-text"
DESIGN_COLORS = ["#7eb8d4", "#a0d4b0", "#f8f8f8", "#c8c8c8", "#888888"]
DEFAULT_COLLECTION_NAME = "instagram_chunks"

# Resolved in _init_paths() when Store is available
UMAP_REDUCER_PATH = Path("dashboard/data/umap_reducer.pkl")
EMBEDDING_COORDS_PATH = Path("dashboard/data/embedding_coords.json")
PLOTLY_OUTPUT_DIR = Path("dashboard/data")


def _init_paths(cfg: dict = None):
    """Resolve module-level path constants from config or Store."""
    global EMBEDDING_MODEL, UMAP_REDUCER_PATH, EMBEDDING_COORDS_PATH, PLOTLY_OUTPUT_DIR
    if cfg is None:
        from personaldb.config import get_config
        cfg = get_config()
    EMBEDDING_MODEL = cfg["models"]["embed"]
    UMAP_REDUCER_PATH = Path(cfg["dashboard"]["umap_reducer_file"])
    EMBEDDING_COORDS_PATH = Path(cfg["dashboard"]["embedding_coords_file"])
    PLOTLY_OUTPUT_DIR = Path(cfg["dashboard"]["plotly_output_dir"])


def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


# ═══════════════════════════════════════════════════
# API-mode functions (imported by server.py)
# ═══════════════════════════════════════════════════

def load_chroma_embeddings(chroma_path: str, cfg: dict = None) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
    """
    Load embeddings + metadata from ChromaDB.
    Returns (embeddings_array, metadata_list).
    metadata_list keys: content, sender_name, timestamp_ms, conversation_id, topic_label
    """
    import chromadb
    collection_name = cfg["embed"]["collection_name"] if cfg else DEFAULT_COLLECTION_NAME
    client = chromadb.PersistentClient(path=chroma_path)
    collection = client.get_collection(name=collection_name)

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
        metadata.append({
            "content": all_docs[i][:300] if i < len(all_docs) else "",
            "sender_name": meta.get("sender_name", meta.get("sender", "")),
            "timestamp_ms": meta.get("timestamp_ms"),
            "conversation_id": meta.get("conversation_id", ""),
            "topic_label": meta.get("topic_label", ""),
            "participants": meta.get("participants", []),
            "chunk_id": meta.get("chunk_id", str(i)),
        })
    log(f"Loaded {len(emb_array)} embeddings from ChromaDB ({total} total)")
    return emb_array, metadata


def reduce_embeddings(
    embeddings: np.ndarray,
    metadata: List[Dict[str, Any]],
    method: str = "umap",
    n_components: int = 2,
    force_refit: bool = False,
) -> Tuple[List[Dict[str, Any]], Any]:
    """
    Reduce embeddings to 2D/3D using specified method.
    Returns (coords_list, reducer_object).
    coords_list: [{x, y, z?, id, text, sender, timestamp, conversation_id, topic}, ...]
    """
    n = len(embeddings)

    if n < 15 and method in ("umap", "tsne"):
        log(f"Warning: only {n} points — falling back to PCA")
        method = "pca"

    reducer_path = UMAP_REDUCER_PATH.parent / f"{method}_{n_components}d_reducer.pkl"

    if reducer_path.exists() and not force_refit:
        log(f"Loading cached {method} reducer from {reducer_path}")
        with open(reducer_path, "rb") as f:
            reducer = pickle.load(f)
        coords_2d = np.array(reducer.transform(embeddings))
    elif method == "umap":
        log(f"Fitting UMAP {n_components}D on {n} points...")
        import umap
        reducer = umap.UMAP(n_neighbors=15, min_dist=0.1, n_components=n_components,
                            metric="cosine", random_state=42)
        coords_2d = reducer.fit_transform(embeddings)
        reducer_path.parent.mkdir(parents=True, exist_ok=True)
        with open(reducer_path, "wb") as f:
            pickle.dump(reducer, f)
    elif method == "tsne":
        log(f"Fitting t-SNE {n_components}D on {n} points (slower)...")
        from sklearn.manifold import TSNE
        reducer = TSNE(n_components=n_components, perplexity=min(30, n-1),
                       random_state=42, n_jobs=-1)
        coords_2d = reducer.fit_transform(embeddings)
        reducer_path.parent.mkdir(parents=True, exist_ok=True)
        with open(reducer_path, "wb") as f:
            pickle.dump(reducer, f)
    else:  # pca
        log(f"Running PCA {n_components}D on {n} points")
        reducer = PCA(n_components=n_components, random_state=42)
        coords_2d = reducer.fit_transform(embeddings)
        reducer_path.parent.mkdir(parents=True, exist_ok=True)
        with open(reducer_path, "wb") as f:
            pickle.dump(reducer, f)

    coords_list = []
    for i in range(len(coords_2d)):
        meta = metadata[i] if i < len(metadata) else {}
        ts = meta.get("timestamp_ms")
        pt = {
            "x": float(coords_2d[i, 0]),
            "y": float(coords_2d[i, 1]),
            "id": i,
            "text": meta.get("content", "")[:200],
            "sender": meta.get("sender_name", "unknown"),
            "timestamp": ts,
            "conversation_id": meta.get("conversation_id", ""),
            "topic": meta.get("topic_label", ""),
        }
        if n_components >= 3:
            pt["z"] = float(coords_2d[i, 2])
        if ts:
            pt["timestamp_iso"] = datetime.fromtimestamp(ts / 1000).isoformat()
        coords_list.append(pt)

    log(f"Reduced to {n_components}D via {method}: {len(coords_list)} points")
    return coords_list, reducer


def search_similar(
    phrase: str,
    reducer: Any,
    coords: List[Dict[str, Any]],
    metadata: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Embed a phrase, transform to reduced space, find nearest neighbors."""
    _check_ollama()
    log(f"Semantic search: '{phrase}'")

    phrase_emb = _get_embedding(phrase)
    query_2d = np.array(reducer.transform(np.array([phrase_emb])))
    qx, qy = float(query_2d[0, 0]), float(query_2d[0, 1])

    distances = []
    for i, pt in enumerate(coords):
        d = np.sqrt((pt["x"] - qx) ** 2 + (pt["y"] - qy) ** 2)
        distances.append((d, i))
    distances.sort(key=lambda x: x[0])

    neighbors = []
    for d, idx in distances[:10]:
        pt = coords[idx]
        neighbors.append({
            "id": idx,
            "distance": round(float(d), 4),
            "text": pt.get("text", "")[:200],
            "sender": pt.get("sender", ""),
            "x": pt["x"],
            "y": pt["y"],
        })

    return {
        "query": phrase,
        "query_coords": {"x": qx, "y": qy},
        "neighbors": neighbors,
    }


def build_timeline_frames(
    coords: List[Dict[str, Any]],
    metadata: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Build time-bucketed frames for animation."""
    valid = [c for c in coords if c.get("timestamp")]
    if not valid:
        return []

    buckets: Dict[str, List[int]] = defaultdict(list)
    for c in valid:
        dt = datetime.fromtimestamp(c["timestamp"] / 1000)
        label = dt.strftime("%Y-%m")
        buckets[label].append(c["id"])

    frames = []
    for label in sorted(buckets.keys()):
        frame_indices = buckets[label]
        frame_coords = []
        for idx in frame_indices:
            if idx < len(coords):
                pt = coords[idx]
                frame_coords.append({
                    "x": pt["x"], "y": pt["y"],
                    "id": pt["id"], "text": pt.get("text", "")[:100],
                    "sender": pt.get("sender", ""),
                })
        frames.append({"time_label": label, "coords": frame_coords})

    return frames


# ═══════════════════════════════════════════════════
# Plotly generation (CLI mode + helpers)
# ═══════════════════════════════════════════════════

def dark_layout(title: str, dim: int = 2) -> Dict[str, Any]:
    layout = dict(
        title=dict(text=title, font=dict(color="#efefef", size=18)),
        paper_bgcolor="#111111",
        plot_bgcolor="#0a0a0a",
        font=dict(color="#c8c8c8"),
        margin=dict(l=40, r=40, t=60, b=40),
        dragmode="lasso",
        hoverlabel=dict(bgcolor="#1a1a1a", font=dict(color="#efefef")),
    )
    if dim == 2:
        layout.update(
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        )
    else:
        layout["scene"] = dict(
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, title=""),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, title=""),
            zaxis=dict(showgrid=False, zeroline=False, showticklabels=False, title=""),
            bgcolor="#0a0a0a",
        )
    return layout


def save_plotly_div(fig: go.Figure, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    div = pio.to_html(fig, full_html=False, include_plotlyjs=False)
    out_path.write_text(div, encoding="utf-8")


def _get_embedding(text: str) -> List[float]:
    payload = {"model": EMBEDDING_MODEL, "prompt": text}
    resp = requests.post(f"{OLLAMA_API_URL}/embeddings", json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()["embedding"]


def _check_ollama() -> None:
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=5)
        resp.raise_for_status()
    except requests.ConnectionError:
        print("Error: Ollama not running. Start with 'ollama serve'.", file=sys.stderr)
        sys.exit(1)


# ── View generators (CLI mode) ────────────────────

def generate_global_map(coords: List[Dict], dim: int = 2) -> go.Figure:
    log("Generating Global Map...")
    senders = sorted(set(c["sender"] for c in coords))
    color_map = {s: DESIGN_COLORS[i % len(DESIGN_COLORS)] for i, s in enumerate(senders)}

    fig = go.Figure()
    for sender in senders:
        subset = [c for c in coords if c["sender"] == sender]
        kwargs = dict(x=[c["x"] for c in subset], y=[c["y"] for c in subset],
                      mode="markers", name=sender,
                      marker=dict(size=5, color=color_map[sender], opacity=0.85,
                                  line=dict(width=0.3, color="#333333")),
                      text=[f"<b>{c['sender']}</b><br>{c.get('text','')[:120]}" for c in subset],
                      hoverinfo="text")
        if dim == 3:
            kwargs["type"] = "scatter3d"
            kwargs["z"] = [c.get("z", 0) for c in subset]
        fig.add_trace(go.Scatter(**kwargs) if dim == 2 else go.Scatter3d(**kwargs))

    fig.update_layout(**dark_layout("Global Conversation Map", dim))
    return fig


def generate_response_pattern(coords: List[Dict], dim: int = 2) -> go.Figure:
    log("Generating Response Pattern Map...")
    convo_groups: Dict[str, List[Dict]] = defaultdict(list)
    for c in coords:
        cid = c.get("conversation_id", "")
        if cid:
            convo_groups[cid].append(c)

    fig = go.Figure()
    ScatterType = go.Scatter if dim == 2 else go.Scatter3d
    base_kwargs = dict(mode="markers", marker=dict(size=3, color="#444444", opacity=0.4),
                       showlegend=False, hoverinfo="none")
    if dim == 2:
        fig.add_trace(go.Scatter(x=[c["x"] for c in coords], y=[c["y"] for c in coords], **base_kwargs))
    else:
        fig.add_trace(go.Scatter3d(x=[c["x"] for c in coords], y=[c["y"] for c in coords],
                                    z=[c.get("z", 0) for c in coords], **base_kwargs))

    colors = DESIGN_COLORS * 50
    for ci, (cid, group) in enumerate(convo_groups.items()):
        if len(group) < 2:
            continue
        group.sort(key=lambda r: r.get("timestamp") or 0)
        color = colors[ci % len(colors)]
        for i in range(len(group) - 1):
            dx = group[i+1]["x"] - group[i]["x"]
            dy = group[i+1]["y"] - group[i]["y"]
            if (dx*dx + dy*dy) ** 0.5 > 15:
                continue
            line_kwargs = dict(x=[group[i]["x"], group[i+1]["x"]],
                               y=[group[i]["y"], group[i+1]["y"]],
                               mode="lines", line=dict(color=color, width=1),
                               showlegend=False, hoverinfo="none")
            fig.add_trace(ScatterType(**line_kwargs))

    fig.update_layout(**dark_layout("Self-Response Pattern Map", dim))
    return fig


def generate_temporal_drift(coords: List[Dict], dim: int = 2) -> go.Figure:
    log("Generating Temporal Drift...")
    valid = [c for c in coords if c.get("timestamp")]
    if not valid:
        fig = go.Figure()
        fig.update_layout(**dark_layout("Temporal Drift (no data)", dim))
        return fig

    for c in valid:
        dt = datetime.fromtimestamp(c["timestamp"] / 1000)
        c["_month_num"] = dt.year * 12 + dt.month

    ScatterType = go.Scatter if dim == 2 else go.Scatter3d
    kwargs = dict(mode="markers",
                  marker=dict(size=5, color=[c["_month_num"] for c in valid],
                             colorscale="Plasma", opacity=0.8,
                             colorbar=dict(title="Month", tickfont=dict(color="#c8c8c8")),
                             line=dict(width=0.3, color="#333333")),
                  text=[f"<b>{c['sender']}</b><br>{c.get('timestamp_iso','')}<br>{c.get('text','')[:100]}"
                        for c in valid],
                  hoverinfo="text")
    if dim == 2:
        fig = go.Figure(go.Scatter(x=[c["x"] for c in valid], y=[c["y"] for c in valid], **kwargs))
    else:
        fig = go.Figure(go.Scatter3d(x=[c["x"] for c in valid], y=[c["y"] for c in valid],
                                      z=[c.get("z", 0) for c in valid], **kwargs))

    fig.update_layout(**dark_layout("Temporal Drift River", dim))
    return fig


def generate_topic_voronoi(coords: List[Dict], dim: int = 2) -> go.Figure:
    log("Generating Topic Voronoi...")
    has_topics = any(c.get("topic", "").strip() for c in coords)
    if not has_topics:
        fig = go.Figure()
        fig.add_annotation(x=0.5, y=0.5, text="No topic clusters.<br>Run run_llm_features.py.",
                           showarrow=False, font=dict(color="#888888", size=16),
                           xref="paper", yref="paper")
        fig.update_layout(**dark_layout("Topic Clusters", dim))
        return fig

    topics: Dict[str, List[Dict]] = defaultdict(list)
    for c in coords:
        label = c.get("topic", "").strip() or "unlabeled"
        topics[label].append(c)

    fig = go.Figure()
    ScatterType = go.Scatter if dim == 2 else go.Scatter3d
    for idx, (label, group) in enumerate(sorted(topics.items())):
        color = DESIGN_COLORS[idx % len(DESIGN_COLORS)]
        cx, cy = np.mean([c["x"] for c in group]), np.mean([c["y"] for c in group])
        kwargs = dict(x=[c["x"] for c in group], y=[c["y"] for c in group],
                      mode="markers", name=f"{label} ({len(group)})",
                      marker=dict(size=5, color=color, opacity=0.8, line=dict(width=0.3, color="#333333")),
                      text=[f"<b>{label}</b><br>{c['sender']}<br>{c.get('text','')[:100]}" for c in group],
                      hoverinfo="text")
        if dim == 3:
            kwargs["z"] = [c.get("z", 0) for c in group]
            kwargs["type"] = "scatter3d"
        fig.add_trace(ScatterType(**kwargs))
        fig.add_annotation(x=cx, y=cy, text=f"<b>{label}</b>", showarrow=False,
                           font=dict(color=color, size=10), bgcolor="rgba(10,10,10,0.8)", borderpad=4)

    fig.update_layout(**dark_layout("Topic Clusters", dim))
    return fig


# ═══════════════════════════════════════════════════
# CLI mode
# ═══════════════════════════════════════════════════

def generate_all_views(chroma_path: str, input_path: str, force: bool) -> None:
    start = time.time()
    _check_ollama()

    emb_array, metadata = load_chroma_embeddings(chroma_path)
    coords, reducer = reduce_embeddings(emb_array, metadata, method="umap", n_components=2, force_refit=force)

    out = PLOTLY_OUTPUT_DIR
    save_plotly_div(generate_global_map(coords, 2), out / "plotly_global_map.html")
    save_plotly_div(generate_response_pattern(coords, 2), out / "plotly_response_pattern.html")
    save_plotly_div(generate_temporal_drift(coords, 2), out / "plotly_temporal_drift.html")
    save_plotly_div(generate_topic_voronoi(coords, 2), out / "plotly_topic_voronoi.html")

    placeholder = go.Figure()
    placeholder.add_annotation(x=0.5, y=0.5, text="Use --query to search.", showarrow=False,
                               font=dict(color="#888888"), xref="paper", yref="paper")
    placeholder.update_layout(**dark_layout("Semantic Field"))
    save_plotly_div(placeholder, out / "plotly_semantic_field.html")

    log(f"All views generated in {time.time() - start:.1f}s")


def main() -> None:
    from personaldb.config import get_config
    from personaldb.store import Store
    cfg = get_config()
    store = Store(cfg)

    _init_paths(cfg)

    default_chroma = str(store.chroma_path)
    default_input = str(store.messages_path)

    parser = argparse.ArgumentParser(description="Visualize ChromaDB embeddings")
    parser.add_argument("--chroma-path", default=default_chroma)
    parser.add_argument("--collection-name", default=DEFAULT_COLLECTION_NAME)
    parser.add_argument("--input", default=default_input)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--query", type=str, default=None)
    args = parser.parse_args()

    PLOTLY_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.query:
        _check_ollama()
        emb_array, metadata = load_chroma_embeddings(args.chroma_path, cfg)
        reducer_path = UMAP_REDUCER_PATH.parent / "umap_2d_reducer.pkl"
        if not reducer_path.exists():
            print("Error: No reducer found. Run without --query first.", file=sys.stderr)
            sys.exit(1)
        with open(reducer_path, "rb") as f:
            reducer = pickle.load(f)
        coords, _ = reduce_embeddings(emb_array, metadata, method="umap", n_components=2)
        result = search_similar(args.query, reducer, coords, metadata)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        generate_all_views(args.chroma_path, args.input, args.force)


# Auto-resolve paths from config when imported (e.g. by server.py)
try:
    _init_paths()
except Exception:
    pass  # use defaults if config is unavailable

if __name__ == "__main__":
    main()

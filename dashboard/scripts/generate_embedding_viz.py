#!/usr/bin/env python3
"""
Embedding visualization module for PersonalDB dashboard.
Projects high-dimensional vector embeddings from ChromaDB into 2D using UMAP
and generates Plotly-based interactive HTML visualizations.

Usage:
    python generate_embedding_viz.py --chroma-path data/chroma --input data/processed/messages.jsonl
    python generate_embedding_viz.py --chroma-path data/chroma --input data/processed/messages.jsonl --force
    python generate_embedding_viz.py --query "how are you doing"
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

import chromadb
import numpy as np
import plotly.graph_objects as go
import plotly.io as pio
import requests
from sklearn.decomposition import PCA

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OLLAMA_API_URL = "http://localhost:11434/api"
EMBEDDING_MODEL = "nomic-embed-text"
DESIGN_COLORS = ["#7eb8d4", "#a0d4b0", "#f8f8f8", "#c8c8c8", "#888888"]
DEFAULT_COLLECTION_NAME = "instagram_chunks"

# Paths set from config in main(); defaults here for direct-import use
UMAP_REDUCER_PATH = Path("dashboard/data/umap_reducer.pkl")
EMBEDDING_COORDS_PATH = Path("dashboard/data/embedding_coords.json")
PLOTLY_OUTPUT_DIR = Path("dashboard/data")


# ---------------------------------------------------------------------------
# Logging utility
# ---------------------------------------------------------------------------

def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


# ---------------------------------------------------------------------------
# ChromaDB helpers
# ---------------------------------------------------------------------------

def load_chromadb_collection(chroma_path: str,
                             collection_name: str = DEFAULT_COLLECTION_NAME
                             ) -> Tuple[Any, List[str], List[List[float]],
                                        List[str], List[Dict[str, Any]]]:
    """
    Load all data from a ChromaDB collection.
    Returns (collection, ids, embeddings, documents, metadatas).
    """
    client = chromadb.PersistentClient(path=chroma_path)
    collection = client.get_collection(name=collection_name)
    count = collection.count()
    if count == 0:
        print("No embeddings found. Run embed.py first.")
        sys.exit(1)
    log(f"Loaded ChromaDB collection '{collection_name}' with {count} items")

    result = collection.get(include=["embeddings", "documents", "metadatas"])
    ids = result["ids"]
    embeddings = result["embeddings"]
    documents = result["documents"] or [""] * len(ids)
    metadatas = result["metadatas"] or [{}] * len(ids)
    return collection, ids, embeddings, documents, metadatas


# ---------------------------------------------------------------------------
# Messages JSONL helpers
# ---------------------------------------------------------------------------

def load_messages_jsonl(input_path: str) -> List[Dict[str, Any]]:
    """Load normalized messages from JSONL file."""
    path = Path(input_path)
    if not path.exists():
        log(f"Warning: {input_path} not found — proceeding without message-level metadata")
        return []
    messages = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                messages.append(json.loads(line))
    log(f"Loaded {len(messages)} messages from {input_path}")
    return messages


def identify_self(messages: List[Dict[str, Any]]) -> str:
    """Identify the user's name from the message senders."""
    if not messages:
        return ""
    senders = [m.get("sender", "") for m in messages if m.get("sender")]
    if not senders:
        return ""
    return Counter(senders).most_common(1)[0][0]


def build_chunk_to_sender_map(
    messages: List[Dict[str, Any]],
    chunk_ids: List[str],
    metadatas: List[Dict[str, Any]],
    self_name: str,
) -> Dict[str, str]:
    """
    Derive a display sender name for each chunk.
    Uses participants metadata: picks the first non-self participant, or
    the conversation title for groups.
    """
    chunk_sender: Dict[str, str] = {}
    for chunk_id, meta in zip(chunk_ids, metadatas):
        participants = meta.get("participants", [])
        if isinstance(participants, str):
            participants = [participants]
        others = [p for p in participants if p != self_name]
        if others:
            chunk_sender[chunk_id] = ", ".join(others[:2])
        else:
            chunk_sender[chunk_id] = meta.get(
                "conversation_title", "unknown"
            )
    return chunk_sender


def parse_timestamp_from_chunk_id(chunk_id: str) -> Optional[int]:
    """
    Extract timestamp_ms from chunk_id format:
    {conversation_id}_{timestamp_ms}_{message_count}
    """
    parts = chunk_id.rsplit("_", 2)
    if len(parts) < 3:
        return None
    try:
        return int(parts[1])
    except (ValueError, IndexError):
        return None


# ---------------------------------------------------------------------------
# Ollama embedding helpers
# ---------------------------------------------------------------------------

def check_ollama() -> None:
    """Verify Ollama is reachable. Exits with error if not."""
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=5)
        resp.raise_for_status()
    except requests.ConnectionError:
        print("Error: Ollama is not running. Start it with 'ollama serve' and try again.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: Could not reach Ollama: {e}")
        sys.exit(1)


def get_embedding(text: str) -> List[float]:
    """Get embedding for a single text via Ollama /api/embeddings."""
    payload = {"model": EMBEDDING_MODEL, "prompt": text}
    resp = requests.post(f"{OLLAMA_API_URL}/embeddings", json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()["embedding"]


# ---------------------------------------------------------------------------
# Dimensionality reduction
# ---------------------------------------------------------------------------

def run_dim_reduction(
    embeddings: np.ndarray,
    reducer_path: Path,
    force: bool,
) -> np.ndarray:
    """
    Run dimensionality reduction. Uses UMAP if >= 50 points, otherwise PCA.
    Caches the fitted reducer to disk.
    Returns 2D coordinates as (N, 2) numpy array.
    """
    n = len(embeddings)

    if reducer_path.exists() and not force:
        log(f"Loading cached reducer from {reducer_path}")
        with open(reducer_path, "rb") as f:
            reducer = pickle.load(f)
        coords = np.array(reducer.transform(embeddings))
        log(f"Transformed {n} points using cached reducer")
        return coords

    if n < 50:
        log(f"Warning: only {n} chunks (< 50). Using PCA instead of UMAP.")
        reducer = PCA(n_components=2, random_state=42)
        coords = reducer.fit_transform(embeddings)
    else:
        log(f"Fitting UMAP on {n} embeddings (this may take a minute)...")
        import umap
        reducer = umap.UMAP(
            n_neighbors=15,
            min_dist=0.1,
            n_components=2,
            metric="cosine",
            random_state=42,
        )
        coords = reducer.fit_transform(embeddings)
        log("UMAP fit complete")

    reducer_path.parent.mkdir(parents=True, exist_ok=True)
    with open(reducer_path, "wb") as f:
        pickle.dump(reducer, f)
    log(f"Saved reducer to {reducer_path}")
    return coords


# ---------------------------------------------------------------------------
# Coordinate + metadata save
# ---------------------------------------------------------------------------

def save_coords_json(
    coords: np.ndarray,
    ids: List[str],
    documents: List[str],
    metadatas: List[Dict[str, Any]],
    chunk_sender: Dict[str, str],
    out_path: Path,
) -> List[Dict[str, Any]]:
    """Save 2D coordinates with metadata to JSON and return the list."""
    records: List[Dict[str, Any]] = []
    for i, chunk_id in enumerate(ids):
        meta = metadatas[i]
        ts = parse_timestamp_from_chunk_id(chunk_id)
        records.append({
            "x": float(coords[i, 0]),
            "y": float(coords[i, 1]),
            "text": documents[i][:200] if documents[i] else "",
            "sender": chunk_sender.get(chunk_id, "unknown"),
            "conversation_id": meta.get("conversation_id", ""),
            "conversation_title": meta.get("conversation_title", ""),
            "timestamp_ms": ts,
            "timestamp_iso": datetime.fromtimestamp(ts / 1000).isoformat() if ts else None,
            "chunk_id": chunk_id,
            "topic_label": meta.get("topic_label", ""),
            "participants": meta.get("participants", []),
            "is_group": meta.get("is_group", False),
        })

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    log(f"Saved {len(records)} coordinate records to {out_path}")
    return records


# ---------------------------------------------------------------------------
# Plotly layout base
# ---------------------------------------------------------------------------

def dark_layout(title: str) -> Dict[str, Any]:
    return dict(
        title=dict(text=title, font=dict(color="#efefef", size=18)),
        paper_bgcolor="#111111",
        plot_bgcolor="#0a0a0a",
        font=dict(color="#c8c8c8"),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        margin=dict(l=40, r=40, t=60, b=40),
    )


def save_plotly_div(fig: go.Figure, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    div = pio.to_html(fig, full_html=False, include_plotlyjs=False)
    out_path.write_text(div, encoding="utf-8")
    log(f"Saved {out_path}")


# ---------------------------------------------------------------------------
# View 1: Global Conversation Map
# ---------------------------------------------------------------------------

def generate_global_map(records: List[Dict[str, Any]]) -> go.Figure:
    log("Generating Global Conversation Map...")
    sender_list = sorted(set(r["sender"] for r in records))
    color_map = {
        s: DESIGN_COLORS[i % len(DESIGN_COLORS)]
        for i, s in enumerate(sender_list)
    }

    fig = go.Figure()
    for sender in sender_list:
        subset = [r for r in records if r["sender"] == sender]
        fig.add_trace(go.Scatter(
            x=[r["x"] for r in subset],
            y=[r["y"] for r in subset],
            mode="markers",
            name=sender,
            marker=dict(size=7, color=color_map[sender], opacity=0.85,
                        line=dict(width=0.5, color="#333333")),
            text=[
                f"<b>{r['sender']}</b><br>"
                f"{r['text'][:120]}<br>"
                f"<i>{r.get('conversation_title', '')}</i>"
                for r in subset
            ],
            hoverinfo="text",
        ))

    fig.update_layout(**dark_layout("Global Conversation Map"))
    fig.update_layout(
        legend=dict(
            x=1.02, y=1,
            font=dict(color="#c8c8c8"),
            bgcolor="rgba(17,17,17,0.8)",
        ),
        hoverlabel=dict(bgcolor="#1a1a1a", font=dict(color="#efefef")),
    )
    return fig


# ---------------------------------------------------------------------------
# View 2: Self-Response Pattern Map
# ---------------------------------------------------------------------------

def generate_response_pattern_map(
    records: List[Dict[str, Any]],
    messages: List[Dict[str, Any]],
) -> go.Figure:
    """
    Draw arrows between consecutive chunks within the same conversation
    to show conversation flow patterns.
    """
    log("Generating Self-Response Pattern Map...")

    # Group records by conversation_id, sort by timestamp
    convo_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in records:
        cid = r.get("conversation_id", "")
        if cid:
            convo_groups[cid].append(r)

    fig = go.Figure()

    # First draw all chunk points in light gray
    all_x = [r["x"] for r in records]
    all_y = [r["y"] for r in records]
    fig.add_trace(go.Scatter(
        x=all_x,
        y=all_y,
        mode="markers",
        name="chunks",
        marker=dict(size=5, color="#444444", opacity=0.5),
        text=[r["sender"] for r in records],
        hoverinfo="text",
        showlegend=False,
    ))

    # Then draw arrows between consecutive chunks per conversation
    color_pool = DESIGN_COLORS * 5
    color_idx = 0
    for cid, group in convo_groups.items():
        if len(group) < 2:
            continue

        group.sort(key=lambda r: r["timestamp_ms"] or 0)
        color = color_pool[color_idx % len(color_pool)]
        color_idx += 1

        for i in range(len(group) - 1):
            src = group[i]
            dst = group[i + 1]
            # Only draw arrow if distance is reasonable (not spanning whole space)
            dx = dst["x"] - src["x"]
            dy = dst["y"] - src["y"]
            dist = (dx * dx + dy * dy) ** 0.5
            if dist > 15:  # Skip very long jumps
                continue

            fig.add_trace(go.Scatter(
                x=[src["x"], dst["x"]],
                y=[src["y"], dst["y"]],
                mode="lines+markers",
                line=dict(color=color, width=1.2),
                marker=dict(size=4, symbol="arrow",
                            angleref="previous", color=color),
                name=group[0].get("conversation_title", cid)[:30],
                text=f"{src.get('timestamp_iso', '')} -> {dst.get('timestamp_iso', '')}",
                hoverinfo="text",
                showlegend=False,
            ))

    fig.update_layout(**dark_layout("Self-Response Pattern Map"))
    return fig


# ---------------------------------------------------------------------------
# View 3: Temporal Drift River
# ---------------------------------------------------------------------------

def generate_temporal_drift(records: List[Dict[str, Any]]) -> go.Figure:
    log("Generating Temporal Drift River...")
    # Filter to records with valid timestamps
    valid = [r for r in records if r.get("timestamp_ms")]
    if not valid:
        log("Warning: No timestamped records for temporal drift view")
        fig = go.Figure()
        fig.update_layout(**dark_layout("Temporal Drift River (no data)"))
        return fig

    # Extract month labels
    for r in valid:
        ts = r["timestamp_ms"]
        dt = datetime.fromtimestamp(ts / 1000)
        r["_month_num"] = dt.year * 12 + dt.month

    min_month = min(r["_month_num"] for r in valid)
    max_month = max(r["_month_num"] for r in valid)

    # Generate month labels for colorbar
    month_labels = []
    for m in range(min_month, max_month + 1):
        y, mo = divmod(m, 12)
        month_labels.append(f"{y}-{mo:02d}")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=[r["x"] for r in valid],
        y=[r["y"] for r in valid],
        mode="markers",
        marker=dict(
            size=7,
            color=[r["_month_num"] for r in valid],
            colorscale="Plasma",
            colorbar=dict(
                title="Month",
                tickvals=list(range(min_month, max_month + 1,
                                    max(1, (max_month - min_month) // 12))),
                ticktext=[month_labels[i - min_month]
                          for i in range(min_month, max_month + 1,
                                         max(1, (max_month - min_month) // 12))],
            ),
            opacity=0.8,
            line=dict(width=0.5, color="#333333"),
        ),
        text=[
            f"<b>{r['sender']}</b><br>"
            f"{r.get('timestamp_iso', '')}<br>"
            f"{r['text'][:100]}"
            for r in valid
        ],
        hoverinfo="text",
    ))

    fig.update_layout(**dark_layout("Temporal Drift River"))
    return fig


# ---------------------------------------------------------------------------
# View 4: Topic Cluster Voronoi
# ---------------------------------------------------------------------------

def generate_topic_voronoi(records: List[Dict[str, Any]]) -> go.Figure:
    log("Generating Topic Cluster Voronoi...")
    # Check if any records have topic_label
    has_topics = any(r.get("topic_label", "").strip() for r in records)

    if not has_topics:
        log("No topic labels found — run run_llm_features.py to generate topic clusters.")
        fig = go.Figure()
        fig.add_annotation(
            x=0.5, y=0.5,
            text="No topic clusters available.<br>Run <i>run_llm_features.py</i> to assign topic labels.",
            showarrow=False,
            font=dict(color="#888888", size=16),
            xref="paper", yref="paper",
        )
        fig.update_layout(**dark_layout("Topic Cluster Voronoi"))
        return fig

    # Group by topic label
    topics: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in records:
        label = r.get("topic_label", "").strip() or "unlabeled"
        topics[label].append(r)

    topic_colors = DESIGN_COLORS * 5
    fig = go.Figure()

    for idx, (label, group) in enumerate(sorted(topics.items())):
        color = topic_colors[idx % len(topic_colors)]
        cx = np.mean([r["x"] for r in group])
        cy = np.mean([r["y"] for r in group])

        fig.add_trace(go.Scatter(
            x=[r["x"] for r in group],
            y=[r["y"] for r in group],
            mode="markers",
            name=f"{label} ({len(group)})",
            marker=dict(size=7, color=color, opacity=0.8,
                        line=dict(width=0.5, color="#333333")),
            text=[
                f"<b>{label}</b><br>{r['sender']}<br>{r['text'][:100]}"
                for r in group
            ],
            hoverinfo="text",
        ))

        # Centroid annotation
        fig.add_annotation(
            x=cx, y=cy,
            text=f"<b>{label}</b>",
            showarrow=False,
            font=dict(color=color, size=11),
            bgcolor="rgba(10,10,10,0.8)",
            borderpad=4,
        )

    fig.update_layout(**dark_layout("Topic Cluster Voronoi"))
    fig.update_layout(
        legend=dict(x=1.02, y=1, font=dict(color="#c8c8c8"),
                     bgcolor="rgba(17,17,17,0.8)"),
    )
    return fig


# ---------------------------------------------------------------------------
# View 5: Semantic Field Query
# ---------------------------------------------------------------------------

def query_embedding(
    phrase: str,
    chroma_path: str = "data/chroma",
    collection_name: str = DEFAULT_COLLECTION_NAME,
) -> Dict[str, Any]:
    """
    Generate embedding for a phrase, transform into UMAP space, and find
    10 nearest neighbors in 2D. Returns JSON-serializable dict.
    """
    check_ollama()
    log(f"Querying semantic field for: '{phrase}'")

    # Get phrase embedding
    phrase_emb = get_embedding(phrase)
    log(f"Generated embedding ({len(phrase_emb)} dims)")

    # Load cached UMAP reducer
    if not UMAP_REDUCER_PATH.exists():
        print("Error: No UMAP reducer found. Run without --query first to fit the reducer.")
        sys.exit(1)
    with open(UMAP_REDUCER_PATH, "rb") as f:
        reducer = pickle.load(f)

    # Transform query into 2D
    query_2d = reducer.transform(np.array([phrase_emb]))
    qx, qy = float(query_2d[0, 0]), float(query_2d[0, 1])

    # Load existing coords
    if not EMBEDDING_COORDS_PATH.exists():
        print("Error: No coordinate data found. Run without --query first.")
        sys.exit(1)
    with open(EMBEDDING_COORDS_PATH, "r", encoding="utf-8") as f:
        records = json.load(f)

    # Find 10 nearest neighbors in 2D space
    distances = []
    for i, r in enumerate(records):
        d = np.sqrt((r["x"] - qx) ** 2 + (r["y"] - qy) ** 2)
        distances.append((d, i))
    distances.sort(key=lambda x: x[0])
    nearest = distances[:10]

    neighbors = []
    for d, idx in nearest:
        r = records[idx]
        neighbors.append({
            "index": idx,
            "distance_2d": round(float(d), 4),
            "chunk_id": r["chunk_id"],
            "text": r["text"],
            "sender": r["sender"],
            "x": r["x"],
            "y": r["y"],
        })

    result = {
        "query": phrase,
        "query_coords": {"x": qx, "y": qy},
        "neighbors": neighbors,
    }

    # Generate and save Plotly semantic field figure
    fig = _build_semantic_field_figure(records, qx, qy, nearest, phrase)

    PLOTLY_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    div = pio.to_html(fig, full_html=False, include_plotlyjs=False)
    (PLOTLY_OUTPUT_DIR / "plotly_semantic_field.html").write_text(div, encoding="utf-8")
    log("Saved plotly_semantic_field.html")

    return result


def _build_semantic_field_figure(
    records: List[Dict[str, Any]],
    qx: float,
    qy: float,
    nearest: List[Tuple[float, int]],
    phrase: str,
) -> go.Figure:
    """Build the Plotly figure for a semantic field query."""
    neighbor_indices = {n[1] for n in nearest}

    fig = go.Figure()

    # Background: all chunks in gray
    fig.add_trace(go.Scatter(
        x=[r["x"] for r in records],
        y=[r["y"] for r in records],
        mode="markers",
        name="all chunks",
        marker=dict(size=4, color="#444444", opacity=0.3),
        text=[r["text"][:80] for r in records],
        hoverinfo="text",
        showlegend=False,
    ))

    # Highlighted neighbors
    neighbor_x = [records[i]["x"] for i in neighbor_indices]
    neighbor_y = [records[i]["y"] for i in neighbor_indices]
    neighbor_text = [
        f"<b>#{rank+1}</b> {records[i]['sender']}<br>{records[i]['text'][:120]}"
        for rank, (_, i) in enumerate(nearest)
    ]

    fig.add_trace(go.Scatter(
        x=neighbor_x,
        y=neighbor_y,
        mode="markers",
        name="neighbors",
        marker=dict(size=10, color="#7eb8d4", opacity=0.9,
                    line=dict(width=2, color="#a0d4b0")),
        text=neighbor_text,
        hoverinfo="text",
    ))

    # Query point: red star
    fig.add_trace(go.Scatter(
        x=[qx],
        y=[qy],
        mode="markers",
        name=f'query: "{phrase}"',
        marker=dict(size=16, symbol="star", color="#ff4444",
                    line=dict(width=2, color="#ffffff")),
        text=[f"<b>Query</b>: {phrase}"],
        hoverinfo="text",
    ))

    # Draw lines from query to neighbors
    for d, i in nearest:
        r = records[i]
        fig.add_trace(go.Scatter(
            x=[qx, r["x"]],
            y=[qy, r["y"]],
            mode="lines",
            line=dict(color="#7eb8d4", width=0.8, dash="dot"),
            showlegend=False,
            hoverinfo="none",
        ))

    fig.update_layout(**dark_layout(f"Semantic Field: \"{phrase}\""))
    fig.update_layout(
        legend=dict(x=1.02, y=1, font=dict(color="#c8c8c8"),
                     bgcolor="rgba(17,17,17,0.8)"),
        hoverlabel=dict(bgcolor="#1a1a1a", font=dict(color="#efefef")),
    )
    return fig


# ---------------------------------------------------------------------------
# Main pipeline (full generation)
# ---------------------------------------------------------------------------

def generate_all_views(
    chroma_path: str,
    input_path: str,
    force: bool,
) -> None:
    """Run the full pipeline: reduce dimensions, save coords, generate views."""
    start = time.time()

    check_ollama()

    # 1. Load ChromaDB
    collection, ids, embeddings, documents, metadatas = load_chromadb_collection(
        chroma_path
    )

    # 2. Load messages JSONL
    messages = load_messages_jsonl(input_path)
    self_name = identify_self(messages)
    if self_name:
        log(f"Identified self as: '{self_name}'")

    # 3. Build sender map
    chunk_sender = build_chunk_to_sender_map(
        messages, ids, metadatas, self_name
    )

    # 4. Dimensionality reduction
    emb_array = np.array(embeddings)
    coords = run_dim_reduction(emb_array, UMAP_REDUCER_PATH, force)

    # 5. Save coordinate records
    records = save_coords_json(
        coords, ids, documents, metadatas, chunk_sender, EMBEDDING_COORDS_PATH
    )

    # 6. Generate and save views
    out_dir = PLOTLY_OUTPUT_DIR

    fig1 = generate_global_map(records)
    save_plotly_div(fig1, out_dir / "plotly_global_map.html")
    log("View 1/5: Global Conversation Map done")

    fig2 = generate_response_pattern_map(records, messages)
    save_plotly_div(fig2, out_dir / "plotly_response_pattern.html")
    log("View 2/5: Self-Response Pattern Map done")

    fig3 = generate_temporal_drift(records)
    save_plotly_div(fig3, out_dir / "plotly_temporal_drift.html")
    log("View 3/5: Temporal Drift River done")

    fig4 = generate_topic_voronoi(records)
    save_plotly_div(fig4, out_dir / "plotly_topic_voronoi.html")
    log("View 4/5: Topic Cluster Voronoi done")

    # View 5: placeholder until --query is used
    placeholder = go.Figure()
    placeholder.add_annotation(
        x=0.5, y=0.5,
        text="Use <b>--query</b> to populate the semantic field view.",
        showarrow=False,
        font=dict(color="#888888", size=16),
        xref="paper", yref="paper",
    )
    placeholder.update_layout(**dark_layout("Semantic Field (placeholder)"))
    save_plotly_div(placeholder, out_dir / "plotly_semantic_field.html")
    log("View 5/5: Semantic Field placeholder done")

    elapsed = time.time() - start
    log(f"All views generated in {elapsed:.1f} seconds")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    # Path hack: allow dashboard/scripts/ to import from src/
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from src.config import get_config
    cfg = get_config()

    # Override module-level constants from config
    global EMBEDDING_MODEL, UMAP_REDUCER_PATH, EMBEDDING_COORDS_PATH, PLOTLY_OUTPUT_DIR
    EMBEDDING_MODEL = cfg["models"]["embed"]
    UMAP_REDUCER_PATH = Path(cfg["dashboard"]["umap_reducer_file"])
    EMBEDDING_COORDS_PATH = Path(cfg["dashboard"]["embedding_coords_file"])
    PLOTLY_OUTPUT_DIR = Path(cfg["dashboard"]["plotly_output_dir"])

    default_chroma = str(cfg["paths"]["chroma"])
    default_input = str(cfg["paths"]["data_processed"]) + "/messages.jsonl"

    parser = argparse.ArgumentParser(
        description="Visualize ChromaDB embeddings in 2D with UMAP + Plotly"
    )
    parser.add_argument(
        "--chroma-path",
        type=str,
        default=default_chroma,
        help=f"Path to ChromaDB persistence directory (default: {default_chroma})",
    )
    parser.add_argument(
        "--collection-name",
        type=str,
        default=DEFAULT_COLLECTION_NAME,
        help=f"ChromaDB collection name (default: {DEFAULT_COLLECTION_NAME})",
    )
    parser.add_argument(
        "--input",
        type=str,
        default=default_input,
        help=f"Path to normalized messages JSONL (default: {default_input})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Refit UMAP even if cached pickle exists",
    )
    parser.add_argument(
        "--query",
        type=str,
        default=None,
        help="Search phrase for semantic field view (prints JSON to stdout)",
    )
    args = parser.parse_args()

    # Ensure plotly output directory exists
    PLOTLY_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.query:
        result = query_embedding(
            args.query,
            chroma_path=args.chroma_path,
            collection_name=args.collection_name,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        generate_all_views(
            chroma_path=args.chroma_path,
            input_path=args.input,
            force=args.force,
        )


if __name__ == "__main__":
    main()

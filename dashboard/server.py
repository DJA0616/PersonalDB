"""
PersonalDB Dashboard Server.

Single-file Flask app that serves the dashboard HTML and provides
interactive API endpoints for embedding visualization.

All visualization data is precomputed by `precompute_embedding_viz.py`.
Server loads JSON files on startup — no live ChromaDB or UMAP at request time.

Usage:
    python dashboard/server.py
    python dashboard/server.py --port 8083 --reload

Precompute viz data first:
    python dashboard/scripts/precompute_embedding_viz.py
"""

import argparse
import json
import os
import pickle
import sys
from pathlib import Path

import numpy as np
import requests
from flask import Flask, jsonify, request, send_from_directory

from personaldb.store import Store

app = Flask(__name__,
            static_folder="static",
            template_folder="templates")

DASHBOARD_DIR = Path(__file__).resolve().parent
store = Store()

# ── Precomputed data (loaded on startup) ──────────
_coords_cache = None       # [{x, y, z?, id, text, sender, timestamp, ...}, ...]
_metadata_cache = None     # [{id, content, sender_name, timestamp_ms, ...}, ...]
_timeline_cache = None     # {"frames": [...]}
_reducer = None            # UMAP reducer (pickle) — for search transforms
_current_dim = 2
_current_method = "umap"

# Ollama embedding config (lazy-resolved to avoid import-time side effects)
_OLLAMA_EMBED_URL = None
_EMBED_MODEL = None


def _ollama_embed_url():
    global _OLLAMA_EMBED_URL
    if _OLLAMA_EMBED_URL is None:
        _OLLAMA_EMBED_URL = store._cfg["ollama"]["api_url"].replace("/api/embeddings", "/api/embed")
    return _OLLAMA_EMBED_URL


def _embed_model():
    global _EMBED_MODEL
    if _EMBED_MODEL is None:
        _EMBED_MODEL = store._cfg["models"]["embed"]
    return _EMBED_MODEL


def _load_precomputed():
    """Load all precomputed viz data from dashboard/data/."""
    global _coords_cache, _metadata_cache, _reducer, _current_dim, _current_method

    data_dir = store.dashboard_data_dir

    # Try 2D first, then 3D
    for dim in (2, 3):
        coords_path = data_dir / f"embedding_coords_{dim}d.json"
        if coords_path.exists():
            with open(coords_path, "r", encoding="utf-8") as f:
                _coords_cache = json.load(f)
            _current_dim = dim
            print(f"[server] Loaded {len(_coords_cache)} coords from {coords_path}")
            break

    meta_path = data_dir / "embedding_metadata.json"
    if meta_path.exists():
        with open(meta_path, "r", encoding="utf-8") as f:
            _metadata_cache = json.load(f)
        print(f"[server] Loaded {len(_metadata_cache)} metadata entries")

    timeline_path = data_dir / "embedding_timeline.json"
    if timeline_path.exists():
        global _timeline_cache
        with open(timeline_path, "r", encoding="utf-8") as f:
            _timeline_cache = json.load(f)
        print(f"[server] Loaded {len(_timeline_cache.get('frames', []))} timeline frames")

    # Load reducer for search
    for method in ("umap", "tsne", "pca"):
        reducer_path = data_dir / f"{method}_{_current_dim}d_reducer.pkl"
        if reducer_path.exists():
            with open(reducer_path, "rb") as f:
                _reducer = pickle.load(f)
            _current_method = method
            print(f"[server] Loaded {method} reducer from {reducer_path}")
            break

    if _coords_cache is None:
        print("[server] Warning: No precomputed coords found.")
        print("  Run: python dashboard/scripts/precompute_embedding_viz.py")


@app.route("/")
def index():
    """Serve the main dashboard HTML."""
    return send_from_directory(str(DASHBOARD_DIR), "index.html")


@app.route("/<path:filename>")
def static_files(filename):
    """Serve static files from dashboard directory."""
    return send_from_directory(str(DASHBOARD_DIR), filename)


@app.route("/api/embedding/status")
def embedding_status():
    """Return current state of the embedding system."""
    n_chunks = 0
    if _metadata_cache:
        n_chunks = len(_metadata_cache)
    elif store.chroma_path.exists():
        try:
            col = store.get_chroma_collection()
            n_chunks = col.count()
        except Exception:
            pass

    return jsonify({
        "n_chunks": n_chunks,
        "methods_available": ["umap", "tsne", "pca"],
        "reducer_fitted": _reducer is not None,
        "current_method": _current_method,
        "current_dim": _current_dim,
        "coords_loaded": _coords_cache is not None,
    })


@app.route("/api/embedding/reduce", methods=["POST"])
def embedding_reduce():
    """Return precomputed coordinates (no live computation)."""
    global _coords_cache, _metadata_cache, _current_method, _current_dim

    data = request.get_json(force=True)
    method = data.get("method", _current_method)
    dim = int(data.get("dim", _current_dim))

    if dim not in (2, 3):
        return jsonify({"error": "dim must be 2 or 3"}), 400

    # If requested dim matches precomputed, return immediately
    if _coords_cache is not None and dim == _current_dim:
        return jsonify({
            "coords": _coords_cache,
            "method": _current_method,
            "dim": _current_dim,
            "n_points": len(_coords_cache),
        })

    # Try loading alternate dimension file
    alt_path = store.dashboard_data_dir / f"embedding_coords_{dim}d.json"
    if alt_path.exists():
        with open(alt_path, "r", encoding="utf-8") as f:
            _coords_cache = json.load(f)
        _current_dim = dim
        return jsonify({
            "coords": _coords_cache,
            "method": _current_method,
            "dim": dim,
            "n_points": len(_coords_cache),
        })

    return jsonify({
        "error": f"No precomputed data for dim={dim}. "
                 f"Run precompute_embedding_viz.py --dim {dim}."
    }), 400


@app.route("/api/embedding/search", methods=["POST"])
def embedding_search():
    """Search for a phrase using precomputed coordinates + live query embedding."""
    global _reducer, _coords_cache, _metadata_cache

    data = request.get_json(force=True)
    phrase = data.get("phrase", "").strip()

    if not phrase:
        return jsonify({"error": "phrase is required"}), 400
    if _reducer is None:
        return jsonify({"error": "No reducer loaded. Run precompute_embedding_viz.py first."}), 400
    if _coords_cache is None:
        return jsonify({"error": "No coordinates loaded. Run precompute_embedding_viz.py first."}), 400

    try:
        # Embed query phrase via Ollama
        payload = {"model": _embed_model(), "prompt": phrase}
        resp = requests.post(_ollama_embed_url(), json=payload, timeout=30)
        resp.raise_for_status()
        phrase_emb = resp.json()["embedding"]

        # Transform via cached reducer
        query_2d = np.array(_reducer.transform(np.array([phrase_emb])))
        qx, qy = float(query_2d[0, 0]), float(query_2d[0, 1])

        # Find nearest neighbors in precomputed coords
        distances = []
        for pt in _coords_cache:
            d = np.sqrt((pt["x"] - qx) ** 2 + (pt["y"] - qy) ** 2)
            distances.append((d, pt["id"]))
        distances.sort(key=lambda x: x[0])

        neighbors = []
        for d, idx in distances[:10]:
            pt = _coords_cache[idx]
            neighbors.append({
                "id": idx,
                "distance": round(float(d), 4),
                "text": pt.get("text", "")[:200],
                "sender": pt.get("sender", ""),
                "x": pt["x"],
                "y": pt["y"],
            })

        return jsonify({
            "query": phrase,
            "query_coords": {"x": qx, "y": qy},
            "neighbors": neighbors,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/embedding/timeline")
def embedding_timeline():
    """Return precomputed timeline frames."""
    global _timeline_cache

    if _timeline_cache is None:
        return jsonify({"error": "No timeline data. Run precompute_embedding_viz.py first."}), 400

    return jsonify(_timeline_cache)


@app.route("/api/embedding/selection", methods=["POST"])
def embedding_selection():
    """Return message details for selected point indices."""
    global _coords_cache

    data = request.get_json(force=True)
    ids = data.get("ids", [])

    if not ids:
        return jsonify({"messages": []})

    if _coords_cache is None:
        return jsonify({"error": "No data loaded."}), 400

    messages = []
    for pt_id in ids:
        idx = int(pt_id)
        if 0 <= idx < len(_coords_cache):
            pt = _coords_cache[idx]
            messages.append({
                "id": idx,
                "text": pt.get("text", "")[:300],
                "sender": pt.get("sender", "Unknown"),
                "timestamp": pt.get("timestamp"),
                "conversation_id": pt.get("conversation_id", "unknown"),
            })

    return jsonify({"messages": messages})


def main():
    parser = argparse.ArgumentParser(description="PersonalDB Dashboard Server")
    parser.add_argument("--port", type=int, default=8083,
                        help="Server port (default: 8083)")
    parser.add_argument("--reload", action="store_true",
                        help="Enable auto-reload on code changes")

    args = parser.parse_args()

    print("[server] Loading precomputed visualization data...")
    _load_precomputed()

    print(f"[server] PersonalDB Dashboard: http://localhost:{args.port}")
    app.run(host="127.0.0.1", port=args.port, debug=args.reload)


if __name__ == "__main__":
    main()

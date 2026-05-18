#!/usr/bin/env python3
"""
Render dashboard HTML from precomputed artifacts.

Reads chart PNGs from dashboard/data/charts/, LLM caches from
dashboard/llm_cache/, and precomputed embedding data — then renders
the Jinja2 template. No Ollama, no ChromaDB, no heavy compute.

Usage:
    python dashboard/scripts/render_dashboard.py
    python dashboard/scripts/render_dashboard.py --skip-llm
    python dashboard/scripts/render_dashboard.py --output path/to/index.html

Output:
    dashboard/index.html
"""

import argparse
import datetime
import json
import os
import sys

from jinja2 import Environment, FileSystemLoader

from personaldb.store import Store

CHART_NAMES = [
    "wordcloud", "pie_per_person", "bar_per_platform",
    "timeline_monthly", "bar_hourly", "hist_msg_length",
    "bar_dow", "noise_report", "chunk_histogram",
]

LLM_CACHE_KEYS = ["conversation_summaries", "topic_clusters", "sentiment_trends"]


def _load_charts(store: Store):
    viz = {}
    for name in CHART_NAMES:
        b64 = store.load_chart_base64(name)
        if b64:
            viz[name] = b64
    return viz


def _load_embedding_context(store: Store):
    """Load precomputed embedding data for the embedding_viz partial."""
    coords = store.load_dashboard_json("embedding_coords_2d") or []
    metadata = store.load_dashboard_json("embedding_metadata") or []
    timeline = store.load_dashboard_json("embedding_timeline") or {}

    # coords/metadata are flat lists; timeline is {"frames": [...]}
    has_embedding = bool(coords) if isinstance(coords, list) else bool(coords and coords.get("items"))

    return {
        "has_embedding": has_embedding,
        "embedding_coords": coords,
        "embedding_metadata": metadata,
        "embedding_timeline": timeline,
    }


def main():
    store = Store()

    parser = argparse.ArgumentParser(description="Render PersonalDB dashboard HTML")
    parser.add_argument("--output",
                        default=str(store._root / store._cfg["paths"]["dashboard_output"]),
                        help="Output path for rendered dashboard HTML")
    parser.add_argument("--skip-llm", action="store_true",
                        help="Skip LLM insights section")
    args = parser.parse_args()

    # -- Load precomputed charts ------------------------------------------------
    print("Loading precomputed charts...")
    viz = _load_charts(store)

    for name in CHART_NAMES:
        status = "found" if viz.get(name) else "missing"
        print(f"  {name}: {status}")

    # -- Overview stats ---------------------------------------------------------
    overview = store.load_dashboard_json("overview") or {
        "total_messages": 0, "total_people": 0, "total_conversations": 0,
    }

    # -- LLM features -----------------------------------------------------------
    llm_data = {}
    has_llm = False

    if not args.skip_llm:
        for key in LLM_CACHE_KEYS:
            llm_data[key] = store.get_llm_cache(f"{key}.json")
        has_llm = any(v is not None for v in llm_data.values())

    if has_llm:
        print("LLM caches loaded.")
    elif not args.skip_llm:
        print("No LLM caches found (run 'features' command first).")

    # -- Embedding context ------------------------------------------------------
    embed_ctx = _load_embedding_context(store)
    if embed_ctx["has_embedding"]:
        print("Precomputed embedding data loaded.")
    else:
        print("No precomputed embedding data (run 'viz precompute' first).")

    # -- Personality analysis ---------------------------------------------------
    personality = store.get_llm_cache("personality_analysis.json")

    # -- Render -----------------------------------------------------------------
    jinja_env = Environment(loader=FileSystemLoader(str(store.template_dir)))
    template = jinja_env.get_template("dashboard.html")

    html = template.render(
        overview=overview,
        wordcloud=viz.get("wordcloud"),
        pie_per_person=viz.get("pie_per_person"),
        bar_per_platform=viz.get("bar_per_platform"),
        timeline_monthly=viz.get("timeline_monthly"),
        bar_hourly=viz.get("bar_hourly"),
        hist_msg_length=viz.get("hist_msg_length"),
        bar_dow=viz.get("bar_dow"),
        noise_report=viz.get("noise_report"),
        chunk_histogram=viz.get("chunk_histogram"),
        has_llm=has_llm,
        conversation_summaries=llm_data.get("conversation_summaries"),
        topic_clusters=llm_data.get("topic_clusters"),
        sentiment_trends=llm_data.get("sentiment_trends"),
        personality=personality,
        embedding_coords=embed_ctx["embedding_coords"],
        embedding_metadata=embed_ctx["embedding_metadata"],
        embedding_timeline=embed_ctx["embedding_timeline"],
        has_embedding=embed_ctx["has_embedding"],
        generated_at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )

    output_path = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(html)

    print(f"Dashboard written to: {output_path}")


if __name__ == "__main__":
    main()

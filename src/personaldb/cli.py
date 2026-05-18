#!/usr/bin/env python3
"""
PersonalDB unified CLI.

Single entry point for all pipeline and dashboard operations.

Usage:
    python -m personaldb.cli ingest --export-root <path> --me <name>
    python -m personaldb.cli preprocess
    python -m personaldb.cli embed
    python -m personaldb.cli retrieve "how are you doing"
    python -m personaldb.cli features
    python -m personaldb.cli personality --me "Daniel"
    python -m personaldb.cli viz
    python -m personaldb.cli dashboard build
    python -m personaldb.cli dashboard serve
"""

import argparse
import sys
from pathlib import Path

from personaldb.store import Store


def _scripts_dir() -> str:
    """Return absolute path to dashboard/scripts/ for local imports."""
    return str(Path(__file__).resolve().parent.parent.parent / "dashboard" / "scripts")


def cmd_ingest(args):
    """Run Instagram message parser."""
    sys.path.insert(0, str(Path(__file__).resolve().parent / "ingest"))
    from personaldb.ingest.instagram_parser import main
    sys.argv = [
        "ingest",
        "--export-root", args.export_root,
        "--me", args.me,
    ]
    if args.list_senders:
        sys.argv.append("--list-senders")
    if args.out:
        sys.argv.extend(["--out", args.out])
    main()


def cmd_preprocess(args):
    """Run message preprocessing."""
    store = Store()
    sys.argv = [
        "preprocess",
        "--input", str(store.messages_path),
        "--output", str(store.chunks_path),
    ]
    from personaldb.preprocess.preprocess import main
    main()


def cmd_embed(args):
    """Run embedding generation."""
    from personaldb.embed.embed import main
    store = Store()
    sys.argv = [
        "embed",
        "--input", str(store.chunks_path),
    ]
    main()


def cmd_retrieve(args):
    """Run semantic retrieval."""
    from personaldb.retrieve.retrieve import main
    sys.argv = [
        "retrieve",
        "--query", args.query,
        "--top-k", str(args.top_k),
    ]
    if args.expand:
        sys.argv.append("--expand")
    if args.hybrid:
        sys.argv.append("--hybrid")
    main()


def cmd_generate(args):
    """Generate a draft reply from context on stdin."""
    from personaldb.generate.generate import main
    sys.argv = ["generate", "--prompt", args.prompt]
    if args.context:
        sys.argv.extend(["--context", args.context])
    else:
        sys.argv.append("--context-stdin")
    main()


def cmd_features(args):
    """Run LLM dashboard features (summaries, clusters, sentiment)."""
    sys.path.insert(0, _scripts_dir())
    from run_llm_features import main
    sys.argv = ["features"]
    if args.force:
        sys.argv.append("--force")
    if args.skip_summaries:
        sys.argv.append("--skip-summaries")
    if args.skip_clusters:
        sys.argv.append("--skip-clusters")
    if args.skip_sentiment:
        sys.argv.append("--skip-sentiment")
    if args.n_clusters:
        sys.argv.extend(["--n-clusters", str(args.n_clusters)])
    main()


def cmd_personality(args):
    """Run personality analysis."""
    sys.path.insert(0, _scripts_dir())
    from analyze_personality import main
    sys.argv = [
        "personality",
        "--me", args.me,
    ]
    if args.force:
        sys.argv.append("--force")
    if args.n_personas:
        sys.argv.extend(["--n-personas", str(args.n_personas)])
    if args.output_report:
        sys.argv.extend(["--output-report", args.output_report])
    main()


def cmd_viz(args):
    """Generate embedding visualizations (Plotly views)."""
    sys.path.insert(0, _scripts_dir())
    from generate_embedding_viz import main
    sys.argv = ["viz"]
    if args.force:
        sys.argv.append("--force")
    if args.query:
        sys.argv.extend(["--query", args.query])
    main()


def cmd_viz_precompute(args):
    """Precompute embedding visualization data for server."""
    sys.path.insert(0, _scripts_dir())
    from precompute_embedding_viz import main
    sys.argv = ["viz-precompute"]
    if args.force:
        sys.argv.append("--force")
    if args.method:
        sys.argv.extend(["--method", args.method])
    if args.dim:
        sys.argv.extend(["--dim", str(args.dim)])
    main()


def cmd_dashboard_build_charts(args):
    """Precompute rule-based charts as PNGs."""
    sys.path.insert(0, _scripts_dir())
    from build_charts import main
    sys.argv = ["build-charts"]
    if args.force:
        sys.argv.append("--force")
    main()


def cmd_dashboard_build(args):
    """Render dashboard HTML from precomputed artifacts."""
    sys.path.insert(0, _scripts_dir())
    from render_dashboard import main
    sys.argv = ["render-dashboard"]
    if args.skip_llm:
        sys.argv.append("--skip-llm")
    if args.output:
        sys.argv.extend(["--output", args.output])
    main()


def cmd_dashboard_serve(args):
    """Start dashboard server (subprocess to isolate Flask)."""
    import subprocess
    cmd = [sys.executable, "dashboard/server.py", "--port", str(args.port)]
    if args.reload:
        cmd.append("--reload")
    if args.precompute:
        cmd.append("--precompute")
    subprocess.run(cmd)


def main():
    parser = argparse.ArgumentParser(
        description="PersonalDB — local message archive analysis toolkit"
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # -- ingest --
    p_ingest = sub.add_parser("ingest", help="Parse Instagram message export")
    p_ingest.add_argument("--export-root", required=True)
    p_ingest.add_argument("--me", required=True)
    p_ingest.add_argument("--list-senders", action="store_true")
    p_ingest.add_argument("--out", default=None)

    # -- preprocess --
    p_pre = sub.add_parser("preprocess", help="Filter, tag, and chunk normalized messages")

    # -- embed --
    p_emb = sub.add_parser("embed", help="Generate embeddings and store in ChromaDB")

    # -- retrieve --
    p_ret = sub.add_parser("retrieve", help="Semantic search over message archive")
    p_ret.add_argument("query", help="Search query text")
    p_ret.add_argument("--top-k", type=int, default=3)
    p_ret.add_argument("--expand", action="store_true", help="Expand query into casual chat variants via LLM")
    p_ret.add_argument("--hybrid", action="store_true", help="Use hybrid BM25+vector search")

    # -- generate --
    p_gen = sub.add_parser("generate", help="Generate draft reply from context")
    p_gen.add_argument("--prompt", required=True)
    p_gen.add_argument("--context", default=None)

    # -- features --
    p_feat = sub.add_parser("features", help="Generate LLM dashboard features")
    p_feat.add_argument("--force", action="store_true")
    p_feat.add_argument("--skip-summaries", action="store_true")
    p_feat.add_argument("--skip-clusters", action="store_true")
    p_feat.add_argument("--skip-sentiment", action="store_true")
    p_feat.add_argument("--n-clusters", type=int, default=None)

    # -- personality --
    p_pers = sub.add_parser("personality", help="Analyze communication personas")
    p_pers.add_argument("--me", required=True)
    p_pers.add_argument("--force", action="store_true")
    p_pers.add_argument("--n-personas", type=int, default=None)
    p_pers.add_argument("--output-report", default=None)

    # -- viz --
    p_viz = sub.add_parser("viz", help="Embedding visualization operations")
    viz_sub = p_viz.add_subparsers(dest="viz_command")

    p_viz_build = viz_sub.add_parser("build", help="Generate Plotly views")
    p_viz_build.add_argument("--force", action="store_true")
    p_viz_build.add_argument("--query", default=None)

    p_viz_pre = viz_sub.add_parser("precompute", help="Precompute coords for server")
    p_viz_pre.add_argument("--force", action="store_true")
    p_viz_pre.add_argument("--method", default=None, choices=["umap", "tsne", "pca"])
    p_viz_pre.add_argument("--dim", type=int, default=None, choices=[2, 3])

    # -- dashboard --
    p_dash = sub.add_parser("dashboard", help="Dashboard operations")
    dash_sub = p_dash.add_subparsers(dest="dash_command")

    p_charts = dash_sub.add_parser("build-charts", help="Precompute rule-based charts")
    p_charts.add_argument("--force", action="store_true")

    p_build = dash_sub.add_parser("build", help="Render dashboard HTML from artifacts")
    p_build.add_argument("--skip-llm", action="store_true")
    p_build.add_argument("--output", default=None)

    p_serve = dash_sub.add_parser("serve", help="Start dashboard server")
    p_serve.add_argument("--port", type=int, default=8083)
    p_serve.add_argument("--reload", action="store_true")
    p_serve.add_argument("--precompute", action="store_true")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    commands = {
        "ingest": cmd_ingest,
        "preprocess": cmd_preprocess,
        "embed": cmd_embed,
        "retrieve": cmd_retrieve,
        "generate": cmd_generate,
        "features": cmd_features,
        "personality": cmd_personality,
    }

    if args.command == "viz":
        if args.viz_command == "build":
            cmd_viz(args)
        elif args.viz_command == "precompute":
            cmd_viz_precompute(args)
        else:
            p_viz.print_help()
    elif args.command == "dashboard":
        if args.dash_command == "build-charts":
            cmd_dashboard_build_charts(args)
        elif args.dash_command == "build":
            cmd_dashboard_build(args)
        elif args.dash_command == "serve":
            cmd_dashboard_serve(args)
        else:
            p_dash.print_help()
    elif args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

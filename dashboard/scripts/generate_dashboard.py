"""
PersonalDB Dashboard Generator

Orchestrates rule-based visualizations, optional LLM feature loading,
and renders the dashboard HTML via Jinja2.

Usage:
    python dashboard/scripts/generate_dashboard.py
    python dashboard/scripts/generate_dashboard.py --input data/processed/messages.jsonl --output dashboard/index.html
    python dashboard/scripts/generate_dashboard.py --skip-llm
"""
import argparse
import datetime
import json
import os
import sys
from collections import Counter, defaultdict

from jinja2 import Environment, FileSystemLoader

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate_rulebased import (
    generate_bar_chart,
    generate_chunk_size_histogram,
    generate_histogram,
    generate_noise_filter_report,
    generate_pie_chart,
    generate_timeline,
    generate_wordcloud,
)


def load_messages(input_path):
    """
    Load messages from a JSONL file and normalize fields for the visualization
    functions, which expect 'content' and 'sender_name' keys.
    """
    messages = []
    with open(input_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            msg = json.loads(line)
            msg["content"] = msg.get("text", "")
            msg["sender_name"] = msg.get("sender", "Unknown")
            msg["platform"] = msg.get("platform", "instagram")
            messages.append(msg)
    return messages


def load_chunks(data_dir):
    """Load chunks.json if it exists."""
    path = os.path.join(data_dir, "chunks.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    return None


def load_llm_results(llm_dir):
    """
    Load cached LLM feature outputs.

    Returns a tuple of (data_dict, has_any).
    data_dict contains keys: conversation_summaries, topic_clusters, sentiment_trends.
    """
    cache = {
        "conversation_summaries": None,
        "topic_clusters": None,
        "sentiment_trends": None,
    }

    paths = {
        "conversation_summaries": os.path.join(llm_dir, "conversation_summaries.json"),
        "topic_clusters": os.path.join(llm_dir, "topic_clusters.json"),
        "sentiment_trends": os.path.join(llm_dir, "sentiment_trends.json"),
    }

    for key, p in paths.items():
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as fh:
                cache[key] = json.load(fh)

    return cache


def compute_overview_stats(messages):
    """Derive total messages, unique people, unique conversations."""
    people = set()
    conversations = set()
    for m in messages:
        people.add(m.get("sender_name", "Unknown"))
        conversations.add(m.get("conversation_id", "unknown"))
    return {
        "total_messages": len(messages),
        "total_people": len(people),
        "total_conversations": len(conversations),
    }


def _safe_timestamp(ts_ms):
    """Convert milliseconds timestamp to datetime, returning None on failure."""
    try:
        return datetime.datetime.fromtimestamp(ts_ms / 1000)
    except (TypeError, OSError, ValueError):
        return None


def generate_all_visualizations(messages):
    """Generate every rule-based chart and return a dict of base64 strings."""
    viz = {}

    # 1 -- Word cloud (overall)
    viz["wordcloud"] = generate_wordcloud(messages)

    # 2 -- Pie chart by sender
    viz["pie_per_person"] = generate_pie_chart(messages, "sender_name", "Message Volume by Person")

    # 3 -- Bar chart by platform
    plat = Counter(m.get("platform", "instagram") for m in messages)
    viz["bar_per_platform"] = generate_bar_chart(
        list(plat.keys()),
        list(plat.values()),
        "Messages by Platform",
        "Platform",
        "Message Count",
        color="#a0d4b0",
    )

    # 4 -- Monthly activity timeline
    monthly = defaultdict(int)
    for m in messages:
        dt = _safe_timestamp(m.get("timestamp_ms"))
        if dt:
            monthly[dt.strftime("%Y-%m")] += 1
    months = sorted(monthly.keys())
    viz["timeline_monthly"] = generate_timeline(
        months,
        [monthly[k] for k in months],
        "Monthly Message Activity",
    )

    # 5 -- Hour-of-day bar chart
    hour_counter = Counter()
    for m in messages:
        dt = _safe_timestamp(m.get("timestamp_ms"))
        if dt:
            hour_counter[dt.hour] += 1
    hour_labels = [f"{h:02d}:00" for h in range(24)]
    viz["bar_hourly"] = generate_bar_chart(
        hour_labels,
        [hour_counter[h] for h in range(24)],
        "Messages by Hour of Day",
        "Hour of Day",
        "Message Count",
    )

    # 6 -- Message length histogram
    lengths = [
        len(m.get("content", ""))
        for m in messages
        if m.get("content", "").strip()
    ]
    bins = min(30, max(5, len(lengths) // 30)) if lengths else 10
    viz["hist_msg_length"] = generate_histogram(
        lengths,
        bins=bins,
        title="Message Length Distribution",
        xlabel="Message Length (characters)",
        ylabel="Frequency",
    )

    # 7 -- Day-of-week bar chart
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    dow = Counter()
    for m in messages:
        dt = _safe_timestamp(m.get("timestamp_ms"))
        if dt:
            dow[day_names[dt.weekday()]] += 1
    viz["bar_dow"] = generate_bar_chart(
        day_names,
        [dow[d] for d in day_names],
        "Messages by Day of Week",
        "Day of Week",
        "Message Count",
    )

    # 8 -- Noise-filter report (detected from content patterns)
    total = len(messages)
    noise_empty = sum(1 for m in messages if not m.get("content", "").strip())
    noise_attachment = sum(
        1 for m in messages if "You sent an attachment" in m.get("content", "")
    )
    noise_reaction = sum(
        1 for m in messages if "Reacted" in m.get("content", "")
    )
    filtered = total - noise_empty - noise_attachment - noise_reaction
    reasons = {}
    if noise_empty:
        reasons["Empty messages"] = noise_empty
    if noise_attachment:
        reasons["Attachments / media"] = noise_attachment
    if noise_reaction:
        reasons["Reaction notifications"] = noise_reaction
    viz["noise_report"] = generate_noise_filter_report(total, filtered, reasons)

    return viz


def generate_chunk_visualization(chunks_data):
    """Produce the chunk-size histogram from cached chunks.json."""
    if not chunks_data or not isinstance(chunks_data, list):
        return generate_chunk_size_histogram([], title="Chunk Size Distribution (No data)")
    sizes = [c.get("message_count", len(c.get("messages", []))) for c in chunks_data]
    return generate_chunk_size_histogram(sizes)


def main():
    # Path hack: allow dashboard/scripts/ to import from src/
    from pathlib import Path as _Path
    sys.path.insert(0, str(_Path(__file__).resolve().parent.parent.parent))
    from src.config import get_config
    cfg = get_config()

    default_input = str(cfg["paths"]["data_processed"]) + "/messages.jsonl"
    default_output = str(cfg["paths"]["dashboard_output"])
    default_chunks = str(cfg["paths"]["data_processed"]) + "/chunks.json"
    default_llm_dir = str(cfg["dashboard"]["llm_cache_dir"])
    default_template_dir = str(cfg["dashboard"]["template_dir"])

    parser = argparse.ArgumentParser(description="Generate PersonalDB dashboard HTML")
    parser.add_argument(
        "--input",
        default=default_input,
        help=f"Path to normalized JSONL messages file (default: {default_input})",
    )
    parser.add_argument(
        "--output",
        default=default_output,
        help=f"Output path for rendered dashboard HTML (default: {default_output})",
    )
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="Skip LLM insights section",
    )
    parser.add_argument(
        "--chunks",
        default=default_chunks,
        help=f"Path to chunks JSON file (default: {default_chunks})",
    )
    parser.add_argument(
        "--llm-dir",
        default=default_llm_dir,
        help=f"Directory containing cached LLM results (default: {default_llm_dir})",
    )
    args = parser.parse_args()

    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    # -- Load messages -----------------------------------------------------------
    input_path = os.path.join(project_root, args.input)
    if not os.path.exists(input_path):
        print(f"Error: input file not found: {input_path}")
        sys.exit(1)

    messages = load_messages(input_path)
    print(f"Loaded {len(messages):,} messages")

    # -- Overview stats ----------------------------------------------------------
    overview = compute_overview_stats(messages)
    print(
        f"  {overview['total_people']} people across "
        f"{overview['total_conversations']} conversations"
    )

    # -- Rule-based visualizations -----------------------------------------------
    print("Generating rule-based visualizations ...")
    viz = generate_all_visualizations(messages)

    # -- Chunk distribution ------------------------------------------------------
    chunks_path = os.path.join(project_root, args.chunks)
    chunks_data = load_chunks(os.path.dirname(chunks_path))
    viz["chunk_histogram"] = generate_chunk_visualization(chunks_data)

    # -- LLM features ------------------------------------------------------------
    llm_data = {
        "conversation_summaries": None,
        "topic_clusters": None,
        "sentiment_trends": None,
    }
    has_llm = False

    if not args.skip_llm:
        llm_dir = os.path.join(project_root, args.llm_dir)
        llm_data = load_llm_results(llm_dir)
        has_llm = any(v is not None for v in llm_data.values())
        if has_llm:
            print("Loaded LLM feature caches.")
        else:
            print(
                "No LLM caches found -- use --skip-llm to suppress, "
                "or run run_llm_features.py first."
            )

    # -- Render ------------------------------------------------------------------
    template_dir = os.path.join(project_root, default_template_dir)
    jinja_env = Environment(loader=FileSystemLoader(template_dir))
    template = jinja_env.get_template("dashboard.html")

    html = template.render(
        overview=overview,
        wordcloud=viz["wordcloud"],
        pie_per_person=viz["pie_per_person"],
        bar_per_platform=viz["bar_per_platform"],
        timeline_monthly=viz["timeline_monthly"],
        bar_hourly=viz["bar_hourly"],
        hist_msg_length=viz["hist_msg_length"],
        bar_dow=viz["bar_dow"],
        noise_report=viz["noise_report"],
        chunk_histogram=viz["chunk_histogram"],
        has_llm=has_llm,
        conversation_summaries=llm_data["conversation_summaries"],
        topic_clusters=llm_data["topic_clusters"],
        sentiment_trends=llm_data["sentiment_trends"],
        generated_at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )

    # -- Write output ------------------------------------------------------------
    output_path = os.path.join(project_root, args.output)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(html)

    print(f"Dashboard written to: {output_path}")


if __name__ == "__main__":
    main()

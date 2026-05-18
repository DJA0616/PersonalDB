#!/usr/bin/env python3
"""
Compute rule-based dashboard charts and save as PNG files.

Run once after messages change. Rendering reads these cached PNGs.
Makes dashboard rebuilds instant when iterating on templates.

Usage:
    python dashboard/scripts/build_charts.py
    python dashboard/scripts/build_charts.py --force

Output:
    dashboard/data/charts/wordcloud.png
    dashboard/data/charts/pie_per_person.png
    dashboard/data/charts/bar_per_platform.png
    dashboard/data/charts/timeline_monthly.png
    dashboard/data/charts/bar_hourly.png
    dashboard/data/charts/hist_msg_length.png
    dashboard/data/charts/bar_dow.png
    dashboard/data/charts/noise_report.png
    dashboard/data/charts/chunk_histogram.png
    dashboard/data/overview.json
"""

import argparse
import datetime
import os
import sys
from collections import Counter, defaultdict

# Local import from dashboard/scripts/
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

from personaldb.store import Store


def compute_overview_stats(messages):
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
    try:
        return datetime.datetime.fromtimestamp(ts_ms / 1000)
    except (TypeError, OSError, ValueError):
        return None


def generate_all_charts(messages, store: Store):
    """Generate all rule-based charts, save as PNGs. Returns viz dict of base64 strings."""
    viz = {}

    def _save(name, b64):
        store.save_chart(name, b64)
        viz[name] = b64

    _save("wordcloud", generate_wordcloud(messages))
    _save("pie_per_person", generate_pie_chart(messages, "sender_name", "Message Volume by Person"))

    plat = Counter(m.get("platform", "instagram") for m in messages)
    _save("bar_per_platform", generate_bar_chart(
        list(plat.keys()), list(plat.values()),
        "Messages by Platform", "Platform", "Message Count", color="#a0d4b0",
    ))

    monthly = defaultdict(int)
    for m in messages:
        dt = _safe_timestamp(m.get("timestamp_ms"))
        if dt:
            monthly[dt.strftime("%Y-%m")] += 1
    months = sorted(monthly.keys())
    _save("timeline_monthly", generate_timeline(
        months, [monthly[k] for k in months], "Monthly Message Activity",
    ))

    hour_counter = Counter()
    for m in messages:
        dt = _safe_timestamp(m.get("timestamp_ms"))
        if dt:
            hour_counter[dt.hour] += 1
    hour_labels = [f"{h:02d}:00" for h in range(24)]
    _save("bar_hourly", generate_bar_chart(
        hour_labels, [hour_counter[h] for h in range(24)],
        "Messages by Hour of Day", "Hour of Day", "Message Count",
    ))

    lengths = [len(m.get("content", "")) for m in messages if m.get("content", "").strip()]
    bins = min(30, max(5, len(lengths) // 30)) if lengths else 10
    _save("hist_msg_length", generate_histogram(
        lengths, bins=bins,
        title="Message Length Distribution",
        xlabel="Message Length (characters)", ylabel="Frequency",
    ))

    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    dow = Counter()
    for m in messages:
        dt = _safe_timestamp(m.get("timestamp_ms"))
        if dt:
            dow[day_names[dt.weekday()]] += 1
    _save("bar_dow", generate_bar_chart(
        day_names, [dow[d] for d in day_names],
        "Messages by Day of Week", "Day of Week", "Message Count",
    ))

    total = len(messages)
    noise_empty = sum(1 for m in messages if not m.get("content", "").strip())
    noise_attachment = sum(1 for m in messages if "You sent an attachment" in m.get("content", ""))
    noise_reaction = sum(1 for m in messages if "Reacted" in m.get("content", ""))
    filtered = total - noise_empty - noise_attachment - noise_reaction
    reasons = {}
    if noise_empty:
        reasons["Empty messages"] = noise_empty
    if noise_attachment:
        reasons["Attachments / media"] = noise_attachment
    if noise_reaction:
        reasons["Reaction notifications"] = noise_reaction
    _save("noise_report", generate_noise_filter_report(total, filtered, reasons))

    return viz


def build_chunk_chart(chunks_data, store: Store):
    """Generate and save chunk-size histogram."""
    if not chunks_data or not isinstance(chunks_data, list):
        b64 = generate_chunk_size_histogram([], title="Chunk Size Distribution (No data)")
    else:
        sizes = [c.get("message_count", len(c.get("messages", []))) for c in chunks_data]
        b64 = generate_chunk_size_histogram(sizes)
    store.save_chart("chunk_histogram", b64)
    return b64


def main():
    store = Store()

    parser = argparse.ArgumentParser(description="Build dashboard charts (compute phase)")
    parser.add_argument("--force", action="store_true",
                        help="Rebuild even if messages haven't changed")
    args = parser.parse_args()

    if not args.force and not store.is_stale("charts", "messages"):
        print("Charts up to date (messages unchanged). Use --force to rebuild.")
        return

    print("Loading messages...")
    messages = store.get_messages()
    print(f"Loaded {len(messages):,} messages")

    overview = compute_overview_stats(messages)
    print(f"  {overview['total_people']} people across {overview['total_conversations']} conversations")

    print("Generating charts...")
    generate_all_charts(messages, store)

    chunks_data = store.get_chunks()
    build_chunk_chart(chunks_data, store)

    store.save_dashboard_json("overview", overview)
    store.mark_fresh("charts", "messages")
    print(f"Charts saved to {store.charts_dir}")


if __name__ == "__main__":
    main()

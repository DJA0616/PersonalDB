#!/usr/bin/env python3
"""
LLM-powered dashboard features for PersonalDB.
Generates conversation summaries, topic clusters, and sentiment trends
using local Ollama models (Llama 3.1 8B + nomic-embed-text).

Usage:
    python dashboard/scripts/run_llm_features.py --input data/processed/messages.jsonl
    python dashboard/scripts/run_llm_features.py --input data/processed/messages.jsonl --force
    python dashboard/scripts/run_llm_features.py --input data/processed/messages.jsonl --n-clusters 7

Output:
    dashboard/llm_cache/conversation_summaries.json
    dashboard/llm_cache/topic_clusters.json
    dashboard/llm_cache/sentiment_trends.json
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import ollama
import numpy as np
from sklearn.cluster import KMeans


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GENERATE_MODEL = "llama3.1:8b"
EMBED_MODEL = "nomic-embed-text"

CACHE_DIR = Path(__file__).resolve().parent.parent / "llm_cache"

EMBED_BATCH_SIZE = 50
CLUSTER_SAMPLE_SIZE = 20
SENTIMENT_SAMPLE_SIZE = 15
SUMMARY_SAMPLE_SIZE = 30

MIN_CONTENT_LENGTH = 20  # skip very short messages for clustering
MIN_SENTIMENT_LENGTH = 10  # skip very short messages for sentiment


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def log(msg: str) -> None:
    """Print a timestamped log message to stdout."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def check_ollama() -> bool:
    """Return True if the local Ollama server is reachable."""
    try:
        ollama.list()
        return True
    except Exception:
        return False


def load_messages(input_path: str) -> List[Dict[str, Any]]:
    """Load normalized messages from a JSON or JSONL file.

    Normalized format (list of objects):
        sender_name, content, timestamp_ms, platform, conversation_id
    """
    path = Path(input_path)
    if not path.exists():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as fh:
        if path.suffix == ".jsonl":
            records: List[Dict[str, Any]] = []
            for line in fh:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
            return records
        data = json.load(fh)

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        # Try common wrapping keys
        for key in ("messages", "records", "data"):
            val = data.get(key)
            if isinstance(val, list):
                return val
        # Fallback: first list-valued key
        for val in data.values():
            if isinstance(val, list):
                return val

    print("Error: could not extract a list of messages from the input file.", file=sys.stderr)
    sys.exit(1)


def load_cache(filename: str) -> Optional[Any]:
    """Load cached JSON data; return None if missing or corrupt."""
    path = CACHE_DIR / filename
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        log(f"Warning: cache file {filename} is corrupt ({exc}); will regenerate.")
        return None


def save_cache(filename: str, data: Any) -> None:
    """Persist data as JSON to the cache directory."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / filename
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def clamp_score(value: float) -> float:
    """Clamp a float to the interval [-1.0, 1.0]."""
    return max(-1.0, min(1.0, value))


def extract_float_from_text(raw: str) -> float:
    """Robustly extract a floating-point number from an LLM response."""
    # Try the whole string first
    stripped = raw.strip()
    try:
        return float(stripped)
    except ValueError:
        pass
    # Look for something that looks like a number
    match = re.search(r"-?\d+\.?\d*", stripped)
    if match:
        return float(match.group())
    return 0.0


# ---------------------------------------------------------------------------
# Feature 1: Conversation Summaries
# ---------------------------------------------------------------------------

def generate_conversation_summaries(
    messages: List[Dict[str, Any]], force: bool = False
) -> Dict[str, Any]:
    """Group messages by conversation_id and ask Ollama to summarize each one.

    Cached to ``dashboard/llm_cache/conversation_summaries.json``.
    """
    cache_file = "conversation_summaries.json"

    if not force:
        cached = load_cache(cache_file)
        if cached is not None:
            log("Conversation summaries: cache hit (use --force to regenerate).")
            return cached

    # Group
    convo_buckets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for msg in messages:
        cid = msg.get("conversation_id", "unknown")
        convo_buckets[cid].append(msg)

    n_convos = len(convo_buckets)
    log(f"Conversation summaries: processing {n_convos} conversations.")

    summaries: Dict[str, Any] = {}
    for idx, (cid, msgs) in enumerate(sorted(convo_buckets.items()), start=1):
        # Collect sender names that appear in this conversation
        senders = sorted(
            {m.get("sender_name", "Unknown") for m in msgs if m.get("sender_name")}
        )

        # Sample messages evenly across the conversation timeline
        n = len(msgs)
        if n <= SUMMARY_SAMPLE_SIZE:
            samples = msgs
        else:
            step = max(1, n // SUMMARY_SAMPLE_SIZE)
            samples = [msgs[j] for j in range(0, n, step)]  # noqa: F841
            samples = samples[:SUMMARY_SAMPLE_SIZE]

        message_block = "\n".join(
            f"  [{m.get('sender_name', '?')}]: {m.get('content', '')[:400]}"
            for m in samples
        )

        is_group = len(senders) > 2
        subject = "this group chat" if is_group else f"{', '.join(senders)}"
        prompt = (
            f"You are analyzing a personal chat archive.\n"
            f"Below are sample messages from a conversation with {subject}.\n\n"
            f"{message_block}\n\n"
            f"Task: Summarize who this person is and what you talk about in 2-3 sentences. "
            f"Focus on the relationship dynamic, recurring topics, and communication tone. "
            f"Be specific and concise. Reply with only the summary, no preamble."
        )

        log(f"  [{idx}/{n_convos}] Summarizing {cid} ({n} msgs, {len(senders)} people)...")

        try:
            response = ollama.generate(model=GENERATE_MODEL, prompt=prompt)
            summary = response.get("response", "").strip()
        except Exception as exc:
            log(f"  Warning: summary failed for {cid}: {exc}")
            summary = f"[Error: {exc}]"

        summaries[cid] = {
            "senders": senders,
            "message_count": n,
            "summary": summary,
            "generated_at": datetime.now().isoformat(),
        }

    save_cache(cache_file, summaries)
    log(f"Conversation summaries: saved {len(summaries)} entries to {CACHE_DIR / cache_file}")
    return summaries


# ---------------------------------------------------------------------------
# Feature 2: Topic Clustering
# ---------------------------------------------------------------------------

def _embed_texts(texts: List[str]) -> List[List[float]]:
    """Batch-embed a list of texts via Ollama (nomic-embed-text)."""
    all_embeddings: List[List[float]] = []
    total = len(texts)
    for start in range(0, total, EMBED_BATCH_SIZE):
        batch = texts[start : start + EMBED_BATCH_SIZE]
        try:
            result = ollama.embed(model=EMBED_MODEL, input=batch)
            all_embeddings.extend(result.get("embeddings", []))
        except Exception as exc:
            log(f"    Embed batch {start // EMBED_BATCH_SIZE + 1} failed: {exc}")
            continue
        done = min(start + EMBED_BATCH_SIZE, total)
        log(f"    Embedded {done}/{total} messages")
    return all_embeddings


def _label_cluster(cluster_msgs: List[Dict[str, Any]], label_idx: int) -> Dict[str, Any]:
    """Ask the LLM to name a topic cluster from its sampled messages."""
    samples = cluster_msgs[:CLUSTER_SAMPLE_SIZE]
    sample_block = "\n".join(
        f"  [{m.get('sender_name', '?')}]: {m.get('content', '')[:300]}"
        for m in samples
    )

    prompt = (
        "You are analyzing a set of personal chat messages that belong to the same "
        "thematic cluster. Below are sample messages from this cluster.\n\n"
        f"{sample_block}\n\n"
        "Task: Give this cluster a short, descriptive name (2-4 words) that captures "
        "the main topic or theme. Examples: 'Daily Plans & Logistics', "
        "'Emotional Support', 'Shared Humor & Memes', 'Work Discussion', "
        "'Food & Restaurants', 'Travel Planning'.\n"
        "Reply with ONLY the cluster name, nothing else. Do not include quotes."
    )

    try:
        response = ollama.generate(model=GENERATE_MODEL, prompt=prompt)
        label = response.get("response", "").strip().strip('"').strip("'")
    except Exception as exc:
        log(f"    Warning: labeling cluster {label_idx} failed: {exc}")
        label = f"Cluster {label_idx}"

    return {
        "label": label,
        "message_count": len(cluster_msgs),
        "sample_texts": [
            m.get("content", "")[:200] for m in samples[:5]
        ],
    }


def generate_topic_clusters(
    messages: List[Dict[str, Any]],
    force: bool = False,
    n_clusters: int = 5,
) -> Dict[str, Any]:
    """Embed message texts with nomic-embed-text, cluster with KMeans, label with LLM.

    Cached to ``dashboard/llm_cache/topic_clusters.json``.
    """
    cache_file = "topic_clusters.json"

    if not force:
        cached = load_cache(cache_file)
        if cached is not None:
            log("Topic clusters: cache hit (use --force to regenerate).")
            return cached

    # Collect messages with enough content
    text_msgs: List[Dict[str, Any]] = []
    texts: List[str] = []
    for msg in messages:
        content = (msg.get("content") or "").strip()
        if len(content) >= MIN_CONTENT_LENGTH:
            text_msgs.append(msg)
            texts.append(content)

    if len(texts) < n_clusters * 2:
        old_k = n_clusters
        n_clusters = max(2, len(texts) // 2)
        log(f"Topic clusters: only {len(texts)} valid messages; reducing k from {old_k} to {n_clusters}.")

    log(f"Topic clusters: embedding {len(texts)} messages (k={n_clusters})...")

    embeddings = _embed_texts(texts)

    if len(embeddings) < n_clusters:
        log(f"Error: only {len(embeddings)} embeddings obtained, need at least {n_clusters}.")
        return {
            "error": "Not enough embeddings generated for clustering.",
            "n_clusters": n_clusters,
            "n_embeddings": len(embeddings),
        }

    log("Topic clusters: running KMeans...")
    emb_array = np.array(embeddings, dtype=np.float32)
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10, max_iter=300)
    labels = kmeans.fit_predict(emb_array)

    # Group messages by cluster label
    cluster_buckets: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for i, label in enumerate(labels.tolist()):
        cluster_buckets[label].append(text_msgs[i])

    log(f"Topic clusters: labeling {len(cluster_buckets)} clusters via LLM...")

    topic_labels: Dict[str, Any] = {}
    for label_idx, cmsgs in sorted(cluster_buckets.items()):
        topic_labels[str(label_idx)] = _label_cluster(cmsgs, label_idx)
        log(f"  Cluster {label_idx} -> '{topic_labels[str(label_idx)]['label']}' "
            f"({len(cmsgs)} messages)")

    result: Dict[str, Any] = {
        "n_clusters": n_clusters,
        "total_messages": len(texts),
        "clusters": topic_labels,
        "generated_at": datetime.now().isoformat(),
    }

    save_cache(cache_file, result)
    log(f"Topic clusters: saved to {CACHE_DIR / cache_file}")
    return result


# ---------------------------------------------------------------------------
# Feature 3: Sentiment Trends
# ---------------------------------------------------------------------------

def generate_sentiment_trends(
    messages: List[Dict[str, Any]], force: bool = False
) -> Dict[str, Any]:
    """Score sentiment per person per month using Ollama.

    Cached to ``dashboard/llm_cache/sentiment_trends.json``.
    """
    cache_file = "sentiment_trends.json"

    if not force:
        cached = load_cache(cache_file)
        if cached is not None:
            log("Sentiment trends: cache hit (use --force to regenerate).")
            return cached

    # Group by (sender_name, year-month)
    person_month: Dict[str, Dict[str, List[str]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for msg in messages:
        sender = msg.get("sender_name", "Unknown")
        ts = msg.get("timestamp_ms")
        if ts is None:
            continue
        try:
            dt = datetime.fromtimestamp(ts / 1000.0)
        except (OSError, ValueError, OverflowError):
            continue
        content = (msg.get("content") or "").strip()
        if len(content) >= MIN_SENTIMENT_LENGTH:
            person_month[sender][dt.strftime("%Y-%m")].append(content)

    n_people = len(person_month)
    log(f"Sentiment trends: processing {n_people} people.")

    trends: Dict[str, Any] = {}
    for sender, months in sorted(person_month.items()):
        total_months = len(months)
        log(f"  {sender}: {total_months} months of data")

        person_trend: Dict[str, Dict[str, Any]] = {}
        for month_key in sorted(months.keys()):
            month_texts = months[month_key]
            samples = month_texts[:SENTIMENT_SAMPLE_SIZE]

            if len(samples) < 2:
                person_trend[month_key] = {
                    "sentiment_score": 0.0,
                    "message_count": len(month_texts),
                    "samples_used": len(samples),
                    "note": "too few messages for reliable scoring",
                }
                continue

            message_block = "\n".join(
                f"  - {t[:400]}" for t in samples
            )

            prompt = (
                "You are analyzing sentiment in personal chat messages. "
                f"Below are messages sent by one person during {month_key}.\n\n"
                f"{message_block}\n\n"
                "Task: Score the overall emotional sentiment of these messages on a "
                "scale from -1.0 (very negative) to 1.0 (very positive). "
                "0.0 is neutral. Consider the tone, word choice, and emotional content. "
                "Reply with ONLY a single floating-point number between -1.0 and 1.0, "
                "nothing else. Example outputs: 0.3, -0.5, 0.0, 0.8"
            )

            try:
                response = ollama.generate(model=GENERATE_MODEL, prompt=prompt)
                raw = response.get("response", "0")
                score = clamp_score(extract_float_from_text(raw))
            except Exception as exc:
                log(f"    Warning: sentiment failed for {sender}/{month_key}: {exc}")
                score = 0.0

            person_trend[month_key] = {
                "sentiment_score": score,
                "message_count": len(month_texts),
                "samples_used": len(samples),
            }

        trends[sender] = person_trend

    result: Dict[str, Any] = {
        "people": trends,
        "generated_at": datetime.now().isoformat(),
    }

    save_cache(cache_file, result)
    log(f"Sentiment trends: saved {len(trends)} people to {CACHE_DIR / cache_file}")
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    # Path hack: allow dashboard/scripts/ to import from src/
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from src.config import get_config
    cfg = get_config()

    # Override module-level constants from config
    global GENERATE_MODEL, EMBED_MODEL, CACHE_DIR
    global EMBED_BATCH_SIZE, CLUSTER_SAMPLE_SIZE, SENTIMENT_SAMPLE_SIZE, SUMMARY_SAMPLE_SIZE
    GENERATE_MODEL = cfg["models"]["generate"]
    EMBED_MODEL = cfg["models"]["embed"]
    CACHE_DIR = Path(cfg["dashboard"]["llm_cache_dir"])
    EMBED_BATCH_SIZE = cfg["ollama"]["embed_batch_size"]
    CLUSTER_SAMPLE_SIZE = cfg["dashboard"]["cluster_sample_size"]
    SENTIMENT_SAMPLE_SIZE = cfg["dashboard"]["sentiment_sample_size"]
    SUMMARY_SAMPLE_SIZE = cfg["dashboard"]["summary_sample_size"]

    default_input = str(cfg["paths"]["data_processed"]) + "/messages.jsonl"
    default_n_clusters = cfg["dashboard"]["n_clusters"]

    parser = argparse.ArgumentParser(
        description="Generate LLM-powered dashboard features for PersonalDB."
    )
    parser.add_argument(
        "--input", type=str, default=default_input,
        help="Path to normalized JSON(L) file of messages "
             "(keys: sender_name, content, timestamp_ms, platform, conversation_id). "
             f"(default: {default_input})"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Regenerate all features even when valid cache files exist."
    )
    parser.add_argument(
        "--n-clusters", type=int, default=default_n_clusters,
        help=f"Number of topic clusters for KMeans (default: {default_n_clusters})."
    )
    parser.add_argument(
        "--skip-summaries", action="store_true",
        help="Skip conversation summary generation."
    )
    parser.add_argument(
        "--skip-clusters", action="store_true",
        help="Skip topic clustering."
    )
    parser.add_argument(
        "--skip-sentiment", action="store_true",
        help="Skip sentiment trend generation."
    )

    args = parser.parse_args()

    log("=== PersonalDB LLM Dashboard Features ===")

    # ------------------------------------------------------------------
    # Pre-flight: Ollama reachable
    # ------------------------------------------------------------------
    log("Checking Ollama connection ...")
    if not check_ollama():
        print(
            "\nError: Ollama is not running or not reachable.\n"
            "  Start it with:  ollama serve\n"
            "  Then ensure the required models are pulled:\n"
            f"    ollama pull {GENERATE_MODEL}\n"
            f"    ollama pull {EMBED_MODEL}\n",
            file=sys.stderr,
        )
        sys.exit(1)
    log("Ollama is running.")

    # ------------------------------------------------------------------
    # Load data
    # ------------------------------------------------------------------
    log(f"Loading messages from {args.input} ...")
    messages = load_messages(args.input)
    log(f"Loaded {len(messages)} messages.")

    if not messages:
        log("No messages found; nothing to do.")
        sys.exit(0)

    # ------------------------------------------------------------------
    # Feature 1: Conversation summaries
    # ------------------------------------------------------------------
    if args.skip_summaries:
        log("Skipping conversation summaries (--skip-summaries).")
    else:
        log("--- Feature 1/3: Conversation Summaries ---")
        generate_conversation_summaries(messages, force=args.force)

    # ------------------------------------------------------------------
    # Feature 2: Topic clusters
    # ------------------------------------------------------------------
    if args.skip_clusters:
        log("Skipping topic clusters (--skip-clusters).")
    else:
        log("--- Feature 2/3: Topic Clustering ---")
        generate_topic_clusters(messages, force=args.force, n_clusters=args.n_clusters)

    # ------------------------------------------------------------------
    # Feature 3: Sentiment trends
    # ------------------------------------------------------------------
    if args.skip_sentiment:
        log("Skipping sentiment trends (--skip-sentiment).")
    else:
        log("--- Feature 3/3: Sentiment Trends ---")
        generate_sentiment_trends(messages, force=args.force)

    log("=== All features complete ===")


if __name__ == "__main__":
    main()

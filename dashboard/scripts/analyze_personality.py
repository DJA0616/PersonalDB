#!/usr/bin/env python3
"""
Personality analysis for PersonalDB.
Identifies distinct communication personas across conversation partners
using local Ollama models.

Two-phase LLM analysis:
  1. Per-conversation style profiles (tone, vocabulary, emotional range, formality)
  2. Cross-conversation persona synthesis (clusters similar styles, names personas)

Usage:
    python dashboard/scripts/analyze_personality.py --input data/processed/messages.jsonl --me "Daniel"
    python dashboard/scripts/analyze_personality.py --input data/processed/messages.jsonl --me "Daniel" --force
    python dashboard/scripts/analyze_personality.py --input data/processed/messages.jsonl --me "Daniel" --output-report report.txt

Output:
    dashboard/llm_cache/personality_analysis.json
    Optional text report (stdout or --output-report file)
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import ollama
import numpy as np
from sklearn.cluster import KMeans

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GENERATE_MODEL = "qwen3:14b"
EMBED_MODEL = "nomic-embed-text"

CACHE_FILE = "personality_analysis.json"

PER_CONVO_SAMPLE_SIZE = 30
MIN_USER_MESSAGES = 5
DEFAULT_N_PERSONAS = 6
CLUSTER_SAMPLE_SIZE = 10
EMBED_BATCH_SIZE = 50

PLACEHOLDER_CONTENT = {
    "you sent an attachment.",
    "you sent a photo.",
    "you sent a video.",
    "you sent a link.",
    "you sent a post.",
    "you sent a story.",
    "you sent a reel.",
    "liked a message",
    "reacted to a message",
    "started a video chat",
    "video chat ended",
}


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def check_ollama() -> bool:
    try:
        ollama.list()
        return True
    except Exception:
        return False




def get_sender(msg: Dict[str, Any]) -> str:
    return msg.get("sender_name") or msg.get("sender") or "Unknown"


def get_content(msg: Dict[str, Any]) -> str:
    return (msg.get("content") or msg.get("text") or "").strip()


def get_convo_id(msg: Dict[str, Any]) -> str:
    return msg.get("conversation_id") or "unknown"


def get_convo_title(msg: Dict[str, Any]) -> str:
    return msg.get("conversation_title") or msg.get("title") or ""


# ---------------------------------------------------------------------------
# Phase 1: Per-conversation style profiles
# ---------------------------------------------------------------------------

def analyze_per_conversation(
    messages: List[Dict[str, Any]], me: str
) -> Dict[str, Any]:
    """Group user's messages by conversation, sample, ask LLM to characterize style."""

    # Group messages by conversation_id, collecting only user's messages
    convo_buckets: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {
            "user_messages": [],
            "participants": set(),
            "title": "",
            "total_messages": 0,
        }
    )

    for msg in messages:
        cid = get_convo_id(msg)
        bucket = convo_buckets[cid]
        bucket["total_messages"] += 1
        bucket["title"] = bucket["title"] or get_convo_title(msg)

        # Gather participants from the explicit participants field
        raw_participants = msg.get("participants") or []
        if isinstance(raw_participants, list):
            for p in raw_participants:
                name = str(p).strip()
                if name:
                    bucket["participants"].add(name)

        sender = get_sender(msg)
        if sender.lower() == me.lower():
            content = get_content(msg)
            if content and content.lower().strip() not in PLACEHOLDER_CONTENT:
                bucket["user_messages"].append(content)

    # Filter: only conversations where user has enough messages
    eligible = {
        cid: b
        for cid, b in convo_buckets.items()
        if len(b["user_messages"]) >= MIN_USER_MESSAGES
    }

    if not eligible:
        return {}

    n_convos = len(eligible)
    log(f"Phase 1: analyzing user style in {n_convos} conversations "
        f"(skipped {len(convo_buckets) - n_convos} with <{MIN_USER_MESSAGES} user msgs).")

    results: Dict[str, Any] = {}
    for idx, (cid, bucket) in enumerate(sorted(eligible.items()), start=1):
        msgs = bucket["user_messages"]
        n = len(msgs)

        # Sample evenly
        if n <= PER_CONVO_SAMPLE_SIZE:
            samples = msgs
        else:
            step = max(1, n // PER_CONVO_SAMPLE_SIZE)
            samples = [msgs[j] for j in range(0, n, step)]
            samples = samples[:PER_CONVO_SAMPLE_SIZE]

        # Build a participants label for the prompt
        others = sorted(bucket["participants"] - {me})
        if not others:
            others = ["Unknown"]
        label = ", ".join(others[:5])
        if len(others) > 5:
            label += f" (+{len(others) - 5} more)"

        message_block = "\n".join(f"  - {t[:400]}" for t in samples)

        prompt = (
            "You are analyzing a personal chat archive to understand the author's "
            "communication style with different people.\n\n"
            f"The author is talking to: {label}\n"
            f"Conversation context: {bucket['title'] or 'unknown'}\n\n"
            f"Below are {len(samples)} sample messages the author sent in this conversation:\n\n"
            f"{message_block}\n\n"
            "Task: Characterize the author's communication style in this conversation. "
            "Respond with ONLY valid JSON (no markdown, no backticks). "
            "Use these exact keys:\n"
            '  "tone": short description of tone (e.g. playful, formal, sarcastic, nurturing),\n'
            '  "vocabulary_signatures": array of 3-5 distinctive words/phrases/patterns used,\n'
            '  "emotional_range": the emotional spectrum shown (e.g. "mostly warm, occasional frustration"),\n'
            '  "formality": one of [very casual, casual, mixed, formal],\n'
            '  "unique_traits": what makes this style different from how they might talk to others\n'
            "Keep values concise, 1-2 sentences each."
        )

        log(f"  [{idx}/{n_convos}] Profiling style with {label} ({n} user msgs)...")

        try:
            response = ollama.generate(model=GENERATE_MODEL, prompt=prompt)
            raw = response.get("response", "").strip()
            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1]
                if raw.endswith("```"):
                    raw = raw[:-3].strip()
                elif raw.endswith("```\n"):
                    raw = raw[:-4].strip()
            profile = json.loads(raw)
        except json.JSONDecodeError:
            log(f"  Warning: could not parse JSON for {cid}, storing raw text.")
            profile = {"raw_response": raw, "parse_error": True}
        except Exception as exc:
            log(f"  Warning: LLM call failed for {cid}: {exc}")
            profile = {"error": str(exc)}

        results[cid] = {
            "participants": sorted(bucket["participants"]),
            "title": bucket["title"],
            "total_messages": bucket["total_messages"],
            "user_message_count": n,
            "style_profile": profile,
        }

    return results


# ---------------------------------------------------------------------------
# Phase 2: Cross-conversation persona synthesis
# ---------------------------------------------------------------------------

def synthesize_personas(
    convo_results: Dict[str, Any], me: str, n_personas: int = DEFAULT_N_PERSONAS
) -> Dict[str, Any]:
    """Embed style profiles, cluster with KMeans, label each cluster with LLM."""

    if not convo_results:
        log("Phase 2: no conversation profiles to synthesize.")
        return {"personas": [], "note": "no data"}

    # Build compact text summaries for embedding
    summaries: List[Dict[str, Any]] = []
    texts: List[str] = []
    for cid, data in sorted(convo_results.items()):
        profile = data.get("style_profile", {})
        if profile.get("parse_error") or profile.get("error"):
            continue
        others = [p for p in data["participants"] if p.lower() != me.lower()]
        text_summary = (
            f"tone: {profile.get('tone', '')}; "
            f"formality: {profile.get('formality', '')}; "
            f"vocab: {', '.join(profile.get('vocabulary_signatures', []))}; "
            f"emotional: {profile.get('emotional_range', '')}; "
            f"traits: {profile.get('unique_traits', '')}"
        )
        summaries.append({
            "conversation_id": cid,
            "with": others,
            "title": data.get("title", ""),
            "profile": profile,
        })
        texts.append(text_summary)

    if not summaries:
        return {"personas": [], "note": "no parseable profiles"}

    n_profiles = len(summaries)
    k = min(n_personas, max(2, n_profiles // 3))
    log(f"Phase 2: clustering {n_profiles} profiles into k={k} via embeddings + KMeans...")

    # Embed all text summaries
    embeddings = _embed_texts(texts)
    if len(embeddings) < k:
        log(f"  Only {len(embeddings)} embeddings; falling back to k=2.")
        k = 2

    # KMeans clustering
    emb_array = np.array(embeddings, dtype=np.float32)
    kmeans = KMeans(n_clusters=k, random_state=42, n_init=10, max_iter=300)
    labels = kmeans.fit_predict(emb_array)

    # Group summaries by cluster label
    cluster_buckets: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for i, label in enumerate(labels.tolist()):
        cluster_buckets[label].append(summaries[i])

    log(f"Phase 2: labeling {len(cluster_buckets)} clusters via LLM...")

    personas: List[Dict[str, Any]] = []
    for label_idx, members in sorted(cluster_buckets.items()):
        persona = _label_persona_cluster(label_idx, members, me)
        personas.append(persona)
        convo_ids = persona.get("conversation_ids", [])
        people = set()
        for m in members:
            people.update(m.get("with", []))
        people_label = ", ".join(sorted(people)[:4])
        if len(people) > 4:
            people_label += f" (+{len(people) - 4})"
        log(f"  Persona {label_idx + 1}: '{persona['name']}' — {len(convo_ids)} convos, with {people_label}")

    return {"personas": personas, "k": k}


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
            log(f"    Embed batch failed: {exc}")
            continue
        done = min(start + EMBED_BATCH_SIZE, total)
        if start % (EMBED_BATCH_SIZE * 5) == 0 or done == total:
            log(f"    Embedded {done}/{total} profiles")
    return all_embeddings


def _label_persona_cluster(
    label_idx: int,
    members: List[Dict[str, Any]],
    me: str,
) -> Dict[str, Any]:
    """Ask LLM to name and describe a persona cluster from its member profiles."""

    convo_ids = [m["conversation_id"] for m in members]
    sample = members[:CLUSTER_SAMPLE_SIZE]

    profile_block = json.dumps(
        [
            {
                "with": m["with"],
                "profile": m["profile"],
            }
            for m in sample
        ],
        ensure_ascii=False,
        indent=2,
    )

    prompt = (
        "You are a communication analyst. Below are style profiles for several "
        "conversations that were algorithmically clustered together because the "
        "author communicates similarly in them.\n\n"
        f"{profile_block}\n\n"
        "Task: These conversations share a common 'persona' or 'voice'. "
        "Give this persona:\n"
        "1. A short, evocative name (e.g. 'The Playful Hype Friend', 'The Earnest Mentor')\n"
        "2. A 1-2 sentence description capturing the core style\n"
        "3. 3-4 defining traits or verbal signatures\n\n"
        "Respond with ONLY valid JSON (no markdown, no backticks):\n"
        '{"name": "...", "description": "...", "defining_traits": ["...", "...", "..."]}'
    )

    try:
        response = ollama.generate(model=GENERATE_MODEL, prompt=prompt)
        raw = response.get("response", "").strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            if raw.endswith("```"):
                raw = raw[:-3].strip()
            elif raw.endswith("```\n"):
                raw = raw[:-4].strip()
        result = json.loads(raw)
    except (json.JSONDecodeError, Exception) as exc:
        log(f"    Warning: labeling cluster {label_idx} failed: {exc}")
        result = {
            "name": f"Style Group {label_idx + 1}",
            "description": "Cluster could not be labeled.",
            "defining_traits": [],
        }

    result["conversation_ids"] = convo_ids
    return result


# ---------------------------------------------------------------------------
# Text report generation
# ---------------------------------------------------------------------------

def generate_report(data: Dict[str, Any], me: str) -> str:
    """Render the analysis as a human-readable text report."""

    lines = []
    lines.append("=" * 60)
    lines.append(f"PERSONALITY ANALYSIS REPORT for {me}")
    lines.append(f"Generated: {data.get('generated_at', 'unknown')}")
    lines.append(f"Model: {data.get('model', GENERATE_MODEL)}")
    lines.append("=" * 60)

    conversations = data.get("conversations", {})
    personas = data.get("personas", {}).get("personas", [])

    # Build inverted map: persona -> conversation details
    persona_map: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    unassigned = []
    for persona in personas:
        for cid in persona.get("conversation_ids", []):
            if cid in conversations:
                persona_map[persona["name"]].append({
                    "cid": cid,
                    "participants": conversations[cid].get("participants", []),
                    "title": conversations[cid].get("title", ""),
                    "profile": conversations[cid].get("style_profile", {}),
                })

    assigned_cids = set()
    for p in personas:
        assigned_cids.update(p.get("conversation_ids", []))

    for cid in conversations:
        if cid not in assigned_cids:
            unassigned.append(cid)

    # Print personas
    lines.append("")
    lines.append(f"PERSONAS IDENTIFIED: {len(personas)}")
    lines.append("")

    for i, persona in enumerate(personas, 1):
        name = persona.get("name", f"Persona {i}")
        desc = persona.get("description", "No description")
        traits = persona.get("defining_traits", [])
        convo_count = len(persona.get("conversation_ids", []))

        lines.append(f"{i}. {name}")
        lines.append(f"   {desc}")
        lines.append(f"   Conversations: {convo_count}")
        if traits:
            lines.append(f"   Traits: {', '.join(traits)}")
        lines.append("")

        # Detail each conversation under this persona
        for entry in persona_map.get(name, []):
            others = [p for p in entry["participants"] if p.lower() != me.lower()]
            label = ", ".join(others[:3])
            if len(others) > 3:
                label += f" (+{len(others) - 3})"
            lines.append(f"     With: {label}")
            profile = entry["profile"]
            if profile and not profile.get("parse_error"):
                lines.append(f"       Tone: {profile.get('tone', '?')}")
                lines.append(f"       Formality: {profile.get('formality', '?')}")
                lines.append(f"       Vocab: {', '.join(profile.get('vocabulary_signatures', []))}")
                lines.append(f"       Emotional: {profile.get('emotional_range', '?')}")
            lines.append("")

    # Unassigned
    if unassigned:
        lines.append(f"UNASSIGNED CONVERSATIONS: {len(unassigned)}")
        for cid in unassigned:
            others = [p for p in conversations[cid].get("participants", [])
                      if p.lower() != me.lower()]
            label = ", ".join(others[:3])
            lines.append(f"  - {label}")
        lines.append("")

    # Stats
    total_convos = len(conversations)
    total_user_msgs = sum(c.get("user_message_count", 0) for c in conversations.values())
    lines.append(f"STATS: {total_convos} conversations, {total_user_msgs:,} user messages analyzed")
    lines.append("=" * 60)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    from personaldb.store import Store
    _store = Store()

    parser = argparse.ArgumentParser(
        description="Analyze communication personas across conversation partners."
    )
    parser.add_argument(
        "--me", type=str, required=True,
        help="Your display name in the chat data."
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Regenerate even when valid cache exists."
    )
    parser.add_argument(
        "--output-report", type=str, default=None,
        help="Write human-readable report to file instead of stdout."
    )
    parser.add_argument(
        "--n-personas", type=int, default=DEFAULT_N_PERSONAS,
        help=f"Target number of personas to identify (default: {DEFAULT_N_PERSONAS})."
    )

    args = parser.parse_args()

    log("=== PersonalDB Personality Analysis ===")

    # ------------------------------------------------------------------
    # Cache check
    # ------------------------------------------------------------------
    if not args.force and not _store.is_stale("personality_analysis", "messages"):
        cached = _store.get_llm_cache(CACHE_FILE)
        if cached is not None:
            log("Cache valid (source unchanged). Use --force to override.")
            report = generate_report(cached, args.me)
            if args.output_report:
                with open(args.output_report, "w", encoding="utf-8") as fh:
                    fh.write(report)
                log(f"Report written to {args.output_report}")
            else:
                print(report)
            return

    # ------------------------------------------------------------------
    # Ollama check
    # ------------------------------------------------------------------
    log("Checking Ollama connection ...")
    if not check_ollama():
        print(
            "\nError: Ollama is not running or not reachable.\n"
            "  Start it with:  ollama serve\n"
            f"  Then ensure the model is pulled:  ollama pull {GENERATE_MODEL}\n",
            file=sys.stderr,
        )
        sys.exit(1)
    log("Ollama is running.")

    # ------------------------------------------------------------------
    # Load data via Store
    # ------------------------------------------------------------------
    log("Loading messages via Store ...")
    messages = _store.get_messages()
    log(f"Loaded {len(messages)} messages.")

    if not messages:
        log("No messages found; nothing to do.")
        sys.exit(0)

    # ------------------------------------------------------------------
    # Phase 1: Per-conversation style profiles
    # ------------------------------------------------------------------
    log("--- Phase 1: Per-Conversation Style Profiles ---")
    convo_results = analyze_per_conversation(messages, args.me)
    log(f"Phase 1 complete: {len(convo_results)} conversations profiled.")

    if not convo_results:
        log("No conversations had enough user messages to analyze. Exiting.")
        sys.exit(0)

    # ------------------------------------------------------------------
    # Phase 2: Persona synthesis
    # ------------------------------------------------------------------
    log("--- Phase 2: Persona Synthesis ---")
    persona_results = synthesize_personas(convo_results, args.me, args.n_personas)
    log(f"Phase 2 complete: {len(persona_results.get('personas', []))} personas identified.")

    # ------------------------------------------------------------------
    # Assemble and cache
    # ------------------------------------------------------------------
    result = {
        "generated_at": datetime.now().isoformat(),
        "user": args.me,
        "model": GENERATE_MODEL,
        "conversations": convo_results,
        "personas": persona_results,
    }

    _store.save_llm_cache(CACHE_FILE, result)
    _store.mark_fresh("personality_analysis", "messages")
    log(f"Results cached to {_store.llm_cache_dir / CACHE_FILE}")

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------
    report = generate_report(result, args.me)
    if args.output_report:
        with open(args.output_report, "w", encoding="utf-8") as fh:
            fh.write(report)
        log(f"Report written to {args.output_report}")
    else:
        print(report)

    log("=== Analysis complete ===")


if __name__ == "__main__":
    main()

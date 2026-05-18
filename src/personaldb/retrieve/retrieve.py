#!/usr/bin/env python3
"""
Retrieval script for PersonalDB.
Combines static style examples and dynamic semantic search from ChromaDB.
Supports query expansion (LLM rewrites query into casual chat variants)
and hybrid BM25+vector search via Reciprocal Rank Fusion.
"""

import json
from pathlib import Path
from typing import List, Dict, Any
import chromadb
from chromadb.config import Settings
import requests
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from personaldb.config import get_config
from personaldb.preprocess.preprocess import normalize_chat_text
from personaldb.retrieve.bm25 import BM25Index


def get_embedding(text: str, model: str, api_url: str) -> List[float]:
    payload = {
        "model": model,
        "prompt": text
    }
    response = requests.post(api_url, json=payload)
    response.raise_for_status()
    return response.json()["embedding"]


def load_static_style_examples(style_examples_path: Path) -> List[str]:
    with open(style_examples_path, 'r', encoding='utf-8') as f:
        content = f.read()
    lines = [line.strip() for line in content.split('\n') if line.strip() and not line.startswith('#')]
    return [line for line in lines if line]


def expand_query(query: str, cfg: dict) -> List[str]:
    """
    Use the LLM to rewrite a research-style query into casual chat variants.
    Returns [original_query] + up to num_variants chat variants.
    Falls back to [original_query] on failure.
    """
    expand_cfg = cfg['retrieve']['expand']
    num_variants = expand_cfg.get('num_variants', 3)
    temperature = expand_cfg.get('temperature', 0.8)
    generate_url = cfg['ollama']['generate_url']
    model = cfg['models']['generate']

    prompt = (
        f"You are a query rewriter. Given a research-style question, rewrite it into "
        f"{num_variants} casual chat variants. The chat is in code-switched Filipino/English "
        f"(Taglish). Make the variants sound like someone searching their own chat history.\n\n"
        f"Example:\n"
        f"Input: \"how do I express affection to close friends\"\n"
        f"Output:\n"
        f"- pano ko ba sinasabi na mahal ko friends ko\n"
        f"- lab u bes ganun ba ko mag express\n"
        f"- how i show love sa close friends ko\n\n"
        f"Now rewrite this query into {num_variants} casual chat variants "
        f"(one per line, just the variants, no numbering):\n"
        f"Query: {query}"
    )

    try:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": 150,
            }
        }
        response = requests.post(generate_url, json=payload, timeout=120)
        response.raise_for_status()
        output = response.json().get("response", "").strip()
        variants = []
        for line in output.split('\n'):
            cleaned = line.strip().lstrip('-* 0123456789.)#')
            if len(cleaned) > 5:
                variants.append(cleaned)
        if variants:
            print(f"Expanded query into {len(variants)} variants: {variants}", file=sys.stderr)
            return [query] + variants[:num_variants]
    except Exception as e:
        print(f"Warning: Query expansion failed ({e}), using original query only", file=sys.stderr)
    return [query]


def vector_search(
    query_embedding: List[float],
    collection,
    top_k: int
) -> List[Dict[str, Any]]:
    """Run pure vector similarity search and return formatted results."""
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k
    )
    formatted = []
    for i in range(len(results['ids'][0])):
        formatted.append({
            'id': results['ids'][0][i],
            'text': results['documents'][0][i],
            'metadata': results['metadatas'][0][i],
            'distance': results['distances'][0][i] if 'distances' in results else None,
        })
    return formatted


def hybrid_search(
    query_embedding: List[float],
    query_text: str,
    collection,
    bm25_index: BM25Index,
    top_k: int,
    rrf_k: int = 60
) -> List[Dict[str, Any]]:
    """
    Combine vector and BM25 search via Reciprocal Rank Fusion.
    Returns results with rrf_score instead of distance.
    """
    # Vector search
    vec_raw = collection.query(query_embeddings=[query_embedding], n_results=top_k)
    vec_by_id: Dict[str, Dict] = {}
    for i in range(len(vec_raw['ids'][0])):
        cid = vec_raw['ids'][0][i]
        vec_by_id[cid] = {
            'id': cid,
            'text': vec_raw['documents'][0][i],
            'metadata': vec_raw['metadatas'][0][i],
            'distance': vec_raw['distances'][0][i],
            'rank_vector': i + 1,
        }

    # BM25 search
    bm25_hits = bm25_index.search(query_text, top_k)
    all_docs = collection.get()
    bm25_by_id: Dict[str, Dict] = {}
    for rank, (doc_idx, bm25_score) in enumerate(bm25_hits, start=1):
        cid = all_docs['ids'][doc_idx]
        bm25_by_id[cid] = {
            'id': cid,
            'text': all_docs['documents'][doc_idx],
            'metadata': all_docs['metadatas'][doc_idx],
            'bm25_score': bm25_score,
            'rank_bm25': rank,
        }

    # RRF merge
    all_ids = set(vec_by_id.keys()) | set(bm25_by_id.keys())
    merged = []
    for cid in all_ids:
        vr = vec_by_id.get(cid)
        br = bm25_by_id.get(cid)
        rrf_score = 0.0
        if vr:
            rrf_score += 1.0 / (rrf_k + vr['rank_vector'])
        if br:
            rrf_score += 1.0 / (rrf_k + br['rank_bm25'])
        base = vr if vr is not None else br
        merged.append({
            'id': cid,
            'text': base['text'],
            'metadata': base['metadata'],
            'distance': vr.get('distance') if vr else None,
            'rrf_score': rrf_score,
        })

    merged.sort(key=lambda r: r['rrf_score'], reverse=True)
    return merged[:top_k]


def main():
    import argparse
    cfg = get_config()

    parser = argparse.ArgumentParser(description='Retrieve context for generation')
    parser.add_argument('--query', type=str, required=True, help='Query text')
    parser.add_argument('--db-path', type=str, default=cfg['paths']['chroma'], help='Path to ChromaDB persistence directory')
    parser.add_argument('--collection-name', type=str, default=cfg['embed']['collection_name'], help='Name of the ChromaDB collection')
    parser.add_argument('--style-examples', type=str, default=cfg['paths']['style_examples'], help='Path to static style examples file')
    parser.add_argument('--top-k', type=int, default=cfg['retrieve']['top_k'], help='Number of dynamic results to retrieve')
    parser.add_argument('--expand', action='store_true', default=cfg['retrieve']['expand'].get('enabled', False), help='Expand query into casual chat variants via LLM')
    parser.add_argument('--hybrid', action='store_true', default=cfg['retrieve']['hybrid'].get('enabled', False), help='Use hybrid BM25+vector search')
    args = parser.parse_args()

    embed_model = cfg['models']['embed']
    ollama_api_url = cfg['ollama']['api_url']
    rrf_k = cfg['retrieve']['hybrid'].get('rrf_k', 60)

    # Load static style examples
    style_path = Path(args.style_examples)
    static_examples = []
    if style_path.exists():
        static_examples = load_static_style_examples(style_path)
        print(f"Loaded {len(static_examples)} static style examples", file=sys.stderr)
    else:
        print(f"Style examples file not found at {style_path}", file=sys.stderr)

    # Initialize ChromaDB
    chroma_client = chromadb.PersistentClient(path=args.db_path)
    try:
        collection = chroma_client.get_collection(name=args.collection_name)
    except Exception:
        print(f"Collection '{args.collection_name}' not found in {args.db_path}", file=sys.stderr)
        collection = None

    dynamic_results = []
    if collection is not None and collection.count() > 0:
        # Build BM25 index once if hybrid mode
        bm25_index = None
        if args.hybrid:
            all_docs = collection.get()
            if all_docs and all_docs['documents']:
                bm25_index = BM25Index()
                bm25_index.index(all_docs['documents'])
                print(f"Built BM25 index with {bm25_index._N} documents", file=sys.stderr)

        # Expand query if requested
        if args.expand:
            variants = expand_query(args.query, cfg)
        else:
            variants = [args.query]

        # Search with each variant
        all_results: List[Dict[str, Any]] = []
        for variant in variants:
            try:
                normalized = normalize_chat_text(variant)
                embedding = get_embedding(normalized, embed_model, ollama_api_url)
            except Exception as e:
                print(f"Failed to embed variant '{variant[:60]}...': {e}", file=sys.stderr)
                continue

            if args.hybrid and bm25_index is not None:
                variant_results = hybrid_search(
                    embedding, normalized, collection, bm25_index, args.top_k, rrf_k
                )
            else:
                variant_results = vector_search(embedding, collection, args.top_k)

            all_results.extend(variant_results)

        # Deduplicate across variants
        seen: Dict[str, Dict[str, Any]] = {}
        for r in all_results:
            cid = r['id']
            if cid not in seen:
                seen[cid] = r
            elif args.hybrid:
                if r.get('rrf_score', 0) > seen[cid].get('rrf_score', 0):
                    seen[cid] = r
            else:
                if r.get('distance', float('inf')) < seen[cid].get('distance', float('inf')):
                    seen[cid] = r

        # Sort and take top_k
        if args.hybrid:
            dynamic_results = sorted(seen.values(), key=lambda r: r.get('rrf_score', 0), reverse=True)[:args.top_k]
        else:
            dynamic_results = sorted(seen.values(), key=lambda r: r.get('distance', float('inf')))[:args.top_k]

        print(f"Retrieved {len(dynamic_results)} results", file=sys.stderr)
    else:
        print("Skipping dynamic retrieval — collection empty or unavailable", file=sys.stderr)

    context = {
        'static_examples': static_examples,
        'dynamic_results': dynamic_results,
        'query': args.query
    }

    print(json.dumps(context, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

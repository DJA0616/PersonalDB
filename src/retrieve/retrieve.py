#!/usr/bin/env python3
"""
Retrieval script for PersonalDB.
Combines static style examples and dynamic semantic search from ChromaDB.
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

from src.config import get_config


def get_embedding(text: str, model: str, api_url: str) -> List[float]:
    """
    Get embedding vector for a text using Ollama's API.
    """
    payload = {
        "model": model,
        "prompt": text
    }
    response = requests.post(api_url, json=payload)
    response.raise_for_status()
    return response.json()["embedding"]


def load_static_style_examples(style_examples_path: Path) -> List[str]:
    """
    Load static style examples from a markdown file.
    Returns a list of example strings.
    """
    # For simplicity, we'll read the file and split by lines that look like examples.
    # In practice, you might have a specific format.
    with open(style_examples_path, 'r', encoding='utf-8') as f:
        content = f.read()
    # Split by double newline and filter out empty lines and markdown headers.
    lines = [line.strip() for line in content.split('\n') if line.strip() and not line.startswith('#')]
    # Further filter: we consider each non-empty line as an example? Or maybe each paragraph.
    # For now, we'll return the lines as examples.
    return [line for line in lines if line]


def main():
    import argparse
    cfg = get_config()

    parser = argparse.ArgumentParser(description='Retrieve context for generation')
    parser.add_argument('--query', type=str, required=True, help='The query text (e.g., the conversation context for which we want to generate a reply)')
    parser.add_argument('--db-path', type=str, default=cfg['paths']['chroma'], help='Path to ChromaDB persistence directory')
    parser.add_argument('--collection-name', type=str, default=cfg['embed']['collection_name'], help='Name of the ChromaDB collection')
    parser.add_argument('--style-examples', type=str, default=cfg['paths']['style_examples'], help='Path to static style examples file')
    parser.add_argument('--top-k', type=int, default=cfg['retrieve']['top_k'], help='Number of dynamic results to retrieve')
    args = parser.parse_args()

    embed_model = cfg['models']['embed']
    ollama_api_url = cfg['ollama']['api_url']

    # Load static style examples
    style_path = Path(args.style_examples)
    static_examples = []
    if style_path.exists():
        static_examples = load_static_style_examples(style_path)
        print(f"Loaded {len(static_examples)} static style examples", file=sys.stderr)
    else:
        print(f"Style examples file not found at {style_path}", file=sys.stderr)

    # Initialize ChromaDB client
    chroma_client = chromadb.PersistentClient(path=args.db_path)
    try:
        collection = chroma_client.get_collection(name=args.collection_name)
    except Exception:
        print(f"Collection '{args.collection_name}' not found in {args.db_path}", file=sys.stderr)
        collection = None

    # Get dynamic results from ChromaDB
    dynamic_results = []
    if collection is not None:
        # Embed the query
        try:
            query_embedding = get_embedding(args.query, embed_model, ollama_api_url)
        except Exception as e:
            print(f"Failed to embed query: {e}", file=sys.stderr)
            query_embedding = None

        if query_embedding is not None:
            # Query the collection
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=args.top_k
            )
            # results is a dict with keys: ids, embeddings, documents, metadatas, distances
            # We want to format the results as a list of dicts with text and metadata.
            for i in range(len(results['ids'][0])):
                dynamic_results.append({
                    'id': results['ids'][0][i],
                    'text': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i],
                    'distance': results['distances'][0][i] if 'distances' in results else None
                })
            print(f"Retrieved {len(dynamic_results)} dynamic results from ChromaDB", file=sys.stderr)
        else:
            print("Skipping dynamic retrieval due to embedding failure", file=sys.stderr)
    else:
        print("Skipping dynamic retrieval because ChromaDB collection is not available", file=sys.stderr)

    # Combine static and dynamic contexts
    # For generation, we might want to present them as a combined list of examples.
    # We'll return a dict with both.
    context = {
        'static_examples': static_examples,
        'dynamic_results': dynamic_results,
        'query': args.query
    }

    # Output as JSON (to be used by the generation script)
    print(json.dumps(context, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()


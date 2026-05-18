#!/usr/bin/env python3
"""
Embedding script for PersonalDB.
Generates embeddings using nomic-embed-text via Ollama and stores in ChromaDB.
"""

import json
import requests
from pathlib import Path
import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any

from personaldb.config import get_config


def get_embeddings_batch(texts: List[str], model: str, api_url: str) -> List[List[float]]:
    """
    Get embedding vectors for a batch of texts using Ollama's /api/embed endpoint.
    Much faster than calling /api/embeddings one-at-a-time.
    """
    payload = {
        "model": model,
        "input": texts
    }
    response = requests.post(api_url, json=payload)
    response.raise_for_status()
    return response.json()["embeddings"]


def main():
    import argparse
    cfg = get_config()

    parser = argparse.ArgumentParser(description='Embed tagged chunks and store in ChromaDB')
    parser.add_argument('--input', type=str, required=True, help='Input JSON file of tagged chunks from preprocess')
    parser.add_argument('--db-path', type=str, default=cfg['paths']['chroma'], help='Path to ChromaDB persistence directory')
    parser.add_argument('--collection-name', type=str, default=cfg['embed']['collection_name'], help='Name of the ChromaDB collection')
    args = parser.parse_args()

    embed_model = cfg['models']['embed']
    ollama_embed_url = cfg['ollama']['api_url'].replace('/api/embeddings', '/api/embed')
    batch_size = cfg['embed'].get('batch_size', cfg.get('ollama', {}).get('embed_batch_size', 50))

    # Load tagged chunks
    input_path = Path(args.input)
    with open(input_path, 'r', encoding='utf-8') as f:
        chunks: List[Dict[str, Any]] = json.load(f)

    # Initialize ChromaDB client with persistence
    chroma_client = chromadb.PersistentClient(path=args.db_path)
    # Get or create collection
    collection = chroma_client.get_or_create_collection(name=args.collection_name)

    # Filter to chunks with text
    valid = [(c, c.get('combined_text', '')) for c in chunks if c.get('combined_text', '')]

    total = 0
    for batch_start in range(0, len(valid), batch_size):
        batch = valid[batch_start:batch_start + batch_size]
        batch_chunks, batch_texts = zip(*batch)

        # Batch embed
        try:
            batch_embeddings = get_embeddings_batch(list(batch_texts), embed_model, ollama_embed_url)
        except Exception as e:
            print(f"Batch {batch_start // batch_size + 1} failed: {e}", flush=True)
            continue

        # Prepare insert
        ids = []
        embeddings = []
        metadatas = []
        documents = []
        for i, chunk in enumerate(batch_chunks):
            chunk_id = chunk.get('chunk_id', f'chunk_{batch_start + i}')
            ids.append(chunk_id)
            embeddings.append(batch_embeddings[i])
            metadatas.append({
                'conversation_id': chunk.get('conversation_id'),
                'conversation_title': chunk.get('conversation_title'),
                'is_group': chunk.get('is_group'),
                'participants': chunk.get('participants'),
                'platform': chunk.get('platform'),
                'relationship_type': chunk.get('relationship_type'),
                'inferred_context': chunk.get('inferred_context'),
                'message_count': chunk.get('message_count'),
            })
            documents.append(batch_texts[i])

        collection.upsert(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=documents)
        total += len(ids)
        print(f"  Batch {batch_start // batch_size + 1}: stored {len(ids)} chunks ({total} total)", flush=True)

    print(f"Done. Collection '{args.collection_name}' has {collection.count()} items.", flush=True)


if __name__ == '__main__':
    main()
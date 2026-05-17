# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Commands

- Install dependencies: `pip install -r requirements.txt`
- Pull Ollama models: `ollama pull nomic-embed-text` and `ollama pull llama3.1:8b`
- Run full pipeline:
  1. Parse Instagram export: `python src/ingest/instagram_parser.py --export-root data/raw --me <your_name> --out data/processed/messages.jsonl`
  2. Preprocess: `python src/preprocess/preprocess.py --input data/processed/messages.jsonl --out data/processed/chunks.json`
  3. Embed: `python src/embed/embed.py --input data/processed/chunks.json`
  4. Retrieve: `python src/retrieve/retrieve.py --query "<your_question>" --top-k 3`
  5. Generate: `python src/retrieve/retrieve.py --query "<your_question>" --top-k 3 | python src/generate/generate.py --context-stdin --prompt "<your_prompt>"`

## Project Architecture

- 6-layer pipeline: Data sources → Preprocessing → Embedding (Ollama/nomic-embed-text) → Vector DB (ChromaDB) → Hybrid retrieval (static style examples + dynamic semantic search) → Generation (Ollama/Llama 3.1 8B)
- Core folders:
  - `src/ingest`: Platform parsers (currently Instagram only)
  - `src/preprocess`: Filter, tag, and chunk conversations
  - `src/embed`: Embed text and write to ChromaDB
  - `src/retrieve`: Hybrid retrieval pipeline
  - `src/generate`: LLM-based response drafts
  - `data/raw`: Exported platform data (ignored by git)
  - `data/processed`: Intermediate JSON outputs
  - `data/chroma`: Persistent vector store
  - `config/style_examples.md`: Curated static style examples (~50)
- Data flow: Raw export → normalized JSONL → filtered/chunked JSON → ChromaDB vectors → retrieval context → LLM draft
- Key constraints: Local-only processing, no API calls, draft-then-approve workflow, Instagram JSON export format with UTF-8 double-encoding fix required
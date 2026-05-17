# PersonalDB

A local-first semantic vector database for personal text corpora. Feed it your conversation exports, notes, or any structured text — then explore patterns, search semantically, visualize your data in embedding space, and optionally generate context-aware drafts. Everything runs on your machine; nothing leaves it.

---

## What it does

Most personal text data sits in opaque exports with no good way to query it. PersonalDB turns those exports into a fully searchable, analyzable semantic database:

- **Semantic search** — retrieve messages or passages by meaning, not keyword
- **Embedding visualization** — project your entire corpus into 2D/3D space to see how topics cluster, how style drifts over time, and what phrases are semantically adjacent
- **Analytics dashboard** — activity timelines, topic clusters, sentiment trends, word frequency, conversation summaries
- **Hybrid retrieval** — combine static curated examples with dynamic semantic search for high-precision context
- **LLM-powered features** — topic labeling, per-conversation summarization, draft generation (all local via Ollama)

---

## Use cases

**Research & self-analysis**
- Discover recurring themes and topic shifts across years of communication
- Track how your vocabulary and tone evolve over time (temporal drift)
- Map semantic neighborhoods: what concepts cluster with what?
- Identify communication pattern differences across relationship types

**Information retrieval**
- Find relevant past conversations by semantic meaning rather than exact wording
- Surface context for ongoing discussions from historical data
- Cluster and label topics automatically across large corpora

**Generation (optional)**
- Retrieve stylistically relevant examples to ground LLM drafts
- Draft context-aware responses that match tone and register from retrieved history

---

## Architecture

Six-layer pipeline, fully local:

```
Data source → Preprocessing → Embedding → Vector DB → Retrieval → Generation
```

1. **Ingest** — platform parsers normalize raw exports into a standard message record format
2. **Preprocess** — filter noise, tag metadata (person, platform, relationship type, context), chunk conversations
3. **Embed** — `nomic-embed-text` via Ollama generates 768-dim vectors; stored in ChromaDB with incremental updates
4. **Vector DB** — ChromaDB persists locally; supports metadata filtering on all retrieval queries
5. **Retrieval** — hybrid: static curated examples always in context + dynamic metadata-filtered semantic search
6. **Generation** — Llama 3.1 8B (or Mistral 7B) via Ollama; draft-then-approve, never auto-sends

### Embedding visualizations

Five interactive views built with UMAP + Plotly, embedded in a static HTML dashboard:

| View | What it reveals |
|---|---|
| Global conversation map | How messages cluster by sender, topic, and style |
| Response pattern map | How reply style shifts based on incoming message type |
| Temporal drift river | Language evolution over months/years |
| Topic cluster Voronoi | KMeans clusters with LLM-generated topic labels |
| Semantic field search | Nearest neighbors of any typed phrase in embedding space |

---

## Tech stack

| Component | Tool |
|---|---|
| Embeddings | `nomic-embed-text` via Ollama |
| Generation | `llama3.1:8b` (or `mistral:7b`) via Ollama |
| Vector store | ChromaDB (local persistence) |
| Dimensionality reduction | UMAP (`umap-learn`) |
| Visualization | Plotly (offline, self-contained HTML) |
| Dashboard | Matplotlib + Plotly + Jinja2 → static HTML |
| Language | Python 3.8+ |
| Hardware target | 16 GB RAM |

---

## Folder structure

```
PersonalDB/
├── src/
│   ├── ingest/        # platform parsers
│   ├── preprocess/    # filter, tag, chunk
│   ├── embed/         # embed + ChromaDB writes
│   ├── retrieve/      # hybrid retrieval
│   └── generate/      # LLM draft generation
├── dashboard/
│   ├── scripts/       # generate_dashboard.py, generate_embedding_viz.py
│   ├── templates/     # Jinja2 HTML partials
│   ├── static/        # CSS + JS
│   └── data/          # cached aggregates, UMAP model, coords JSON
├── config/
│   └── style_examples.md   # curated retrieval examples (~50)
└── data/
    ├── raw/           # raw platform exports (git-ignored)
    ├── processed/     # normalized JSONL + chunks
    └── chroma/        # vector DB persistence
```

---

## Quick start

### Prerequisites

- [Ollama](https://ollama.com) installed and running
- Python 3.8+

```bash
ollama pull nomic-embed-text
ollama pull llama3.1:8b
pip install -r requirements.txt
```

### Run the pipeline

```bash
# 1. Parse export (Instagram shown; adjust parser for other platforms)
python src/ingest/instagram_parser.py \
  --export-root data/raw \
  --me <your_display_name> \
  --out data/processed/messages.jsonl

# 2. Preprocess: filter, tag, chunk
python src/preprocess/preprocess.py \
  --input data/processed/messages.jsonl \
  --out data/processed/chunks.json

# 3. Embed into ChromaDB
python src/embed/embed.py --input data/processed/chunks.json

# 4. Semantic search
python src/retrieve/retrieve.py --query "your question here" --top-k 5

# 5. Generate a draft (pipe retrieval output into generate)
python src/retrieve/retrieve.py --query "your question" --top-k 3 \
  | python src/generate/generate.py --context-stdin --prompt "your prompt"

# 6. Build dashboard + embedding visualizations
python dashboard/scripts/generate_dashboard.py
# then open dashboard/index.html
```

See [QUICKSTART.md](QUICKSTART.md) for step-by-step setup with example data.

---

## Supported data sources

| Platform | Status |
|---|---|
| Instagram (JSON export) | Supported |
| Others | Planned — add a parser in `src/ingest/` |

The ingest layer is designed to be extended. Any data source that can be normalized to `{sender, timestamp_ms, content, metadata}` records works with the rest of the pipeline unchanged.

---

## Privacy

All processing is local. No data is sent to any external service. The `data/` directory is git-ignored by default — raw exports and processed outputs stay on disk only.

---

## Status

Active development. Core pipeline (ingest → embed → retrieve → generate) is functional. Dashboard and embedding visualizations are in progress.

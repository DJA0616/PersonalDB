# PersonalDB — Plan

## Goal
Local AI assistant that drafts message replies in my tone when I'm too tired
to write them myself. Fully private, runs on my machine, draft-then-approve
(never auto-sends).

## Core decisions
- **Local-only.** No API calls, no cloud, no logs. Messages never leave the machine.
- **No fine-tuning.** Hybrid retrieval + good in-context examples gets ~90% there.
- **Draft mode, not auto-send.** Agent writes, I approve/edit before sending.
- **Preprocessing is pure Python.** Rule-based filters, no LLM. LLM only touches
  final draft generation.
- **First platform: Instagram** (JSON export).

## Architecture (6 layers)
1. **Data sources** — export sent messages (Instagram first; others later)
2. **Preprocessing** — filter noise → tag metadata → chunk conversations
3. **Embedding** — nomic-embed-text via Ollama, local
4. **Vector DB** — ChromaDB, local persistence
5. **Hybrid retrieval** — static style layer (~50 curated examples, always in
   context) + dynamic layer (metadata-filtered semantic search)
6. **Generation** — Llama 3.1 8B / Mistral 7B via Ollama, drafts reply

## Tech stack
- Ollama — `llama3.1:8b` (generation) + `nomic-embed-text` (embeddings)
- ChromaDB — vector store
- Python — preprocessing, retrieval, glue
- Hardware target: 16GB RAM

## Instagram export specifics
- Export format: JSON (confirmed).
- Messages live in `your_instagram_activity/messages/inbox/` — verify exact
  top-level folder name once the download lands; Instagram renames it occasionally.
  Parser auto-locates `messages/inbox` to be safe.
- One folder per conversation; each holds `message_1.json` (long threads split
  into `message_2.json`, etc.).
- Each JSON: `participants` + `messages` array. Messages have `sender_name`,
  `timestamp_ms`, `content`.
- **Encoding bug:** exports are double-encoded UTF-8. Every string must be fixed
  with `text.encode('latin-1').decode('utf-8')`.
- Sent-only filter: `sender_name` == my display name.
- Skip messages with no `content` — those are photos, shares, calls.
- `len(participants) > 2` → group DM (feeds relationship metadata).

## Preprocessing rules
- Drop messages under ~10 words
- Drop emoji-only / pure acknowledgements ("ok", "lol", "haha yeah")
- Tag each chunk: person, platform, relationship type, inferred context
- Group consecutive messages per conversation into chunks (preserves tone flow)

## Embedding notes
- Modular: each chunk has a unique ID
- Incremental updates — embed only new messages, insert by ID
- Full re-embed ONLY if switching embedding model (vectors incompatible)

## Folder structure
```
PersonalDB/
├── PLAN.md
├── README.md
├── requirements.txt
├── data/
│   ├── raw/          # extracted Instagram export
│   ├── processed/    # normalized + chunked output
│   └── chroma/       # vector DB persistence
├── src/
│   ├── ingest/       # platform parsers  <- instagram_parser.py
│   ├── preprocess/   # filter, tag, chunk
│   ├── embed/        # embedding + ChromaDB writes
│   ├── retrieve/     # hybrid retrieval
│   └── generate/     # LLM draft generation
├── config/
│   └── style_examples.md   # curated ~50 examples (static layer)
└── scripts/          # initial_embed, incremental_update
```

## Build phases
1. Scaffold folders + install Ollama, pull models
2. [in progress] Instagram parser — normalize export to message records
3. Preprocessing script (filter → tag → chunk)
4. Initial embed into ChromaDB
5. Curate ~50 best style examples manually
6. Retrieval + generation glue; CLI or simple UI

## Open questions
- Manual relationship tagging vs auto-classify
- CLI vs simple GUI for the draft interface

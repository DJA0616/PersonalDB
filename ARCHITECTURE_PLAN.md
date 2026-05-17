# Architecture Plan — Remaining Features & Branch Strategy

## Branch Strategy

```
master          ← stable, tested, dashboard-renderable
  ├── fix/emoji-detection
  ├── fix/logging-migration
  ├── feat/config-system
  ├── feat/test-suite
  ├── feat/embedding-viz-integration
  ├── feat/relationship-tagging
  ├── feat/style-curation-tools
  ├── feat/gui-draft-interface
  ├── feat/platform-messenger
  └── feat/incremental-embed
```

Merge rule: branch → `master` only after syntax check passes AND dashboard still renders.

## Architecture Extensions

### 1. Config System (`feat/config-system`)
**Problem**: Model names, chunk sizes, thresholds, file paths all hardcoded across 5+ scripts.

**Design**:
```
config/
  defaults.yaml       ← all defaults, checked into git
  local.yaml          ← user overrides, gitignored
```

**New module**: `src/config.py`
```python
# Single loader used by every script
from src.config import load_config
cfg = load_config()  # merges defaults.yaml + local.yaml (if exists)
```

**Key values to extract**:
- `models.embed`, `models.generate`
- `preprocess.min_words`, `preprocess.max_chunk_size`
- `preprocess.acknowledgements` (extendable list)
- `paths.data_raw`, `paths.data_processed`, `paths.chroma`
- `ollama.api_url`
- All dashboard paths

**Scripts touched**: All 5 src/ scripts + all 4 dashboard/ scripts.

---

### 2. Logging Migration (`fix/logging-migration`)
**Problem**: `print()` everywhere, no levels, no file output.

**Design**: Replace all `print()` with `logging.getLogger(__name__)`.
- `INFO`: progress milestones
- `DEBUG`: per-message/per-chunk detail
- `WARNING`: recoverable errors (Ollama timeout, corrupt cache)
- `ERROR`: fatal stops

**New module**: `src/logging_setup.py` — configures root logger once.
**CLI flag**: `--verbose` / `--debug` on every script.

---

### 3. Test Suite (`feat/test-suite`)
**Framework**: `pytest`

```
tests/
  conftest.py                   ← shared fixtures (sample messages, mock Ollama)
  test_instagram_parser.py      ← encoding fix, field mapping, edge cases
  test_preprocess.py            ← filtering, chunking, emoji detection
  test_embed.py                 ← mock Ollama, ChromaDB write/read
  test_retrieve.py              ← mock ChromaDB, style examples loading
  test_generate.py              ← prompt building, mock Ollama response
  test_dashboard_rulebased.py   ← each viz function with known input
  test_dashboard_llm.py         ← mock Ollama, cache hit/miss
  test_dashboard_orchestration.py ← full pipeline with sample data
```

**CI potential**: `python -m pytest tests/` runs offline (mock external deps).

---

### 4. Emoji Detection Fix (`fix/emoji-detection`)
**Problem**: `is_emoji_only()` in `src/preprocess/preprocess.py` uses broken regex `r'[\s\U00010000-\U0010ffff]'`.

**Fix**: Use `emoji` library (already in requirements) or Unicode category check.
```python
import emoji
def is_emoji_only(text):
    return bool(text.strip()) and all(c in emoji.EMOJI_DATA or c.isspace() for c in text)
```
Also expand acknowledgement set (currently English-centric, 8 items).

---

### 5. Embedding Viz Integration (`feat/embedding-viz-integration`)
**Problem**: `generate_embedding_viz.py` exists standalone, not wired into dashboard.

**What's needed**:

**New file**: `dashboard/static/js/embedding_viz.js`
- Tab switcher for 5 views
- Search box → calls `generate_embedding_viz.py --query "..."` (subprocess via Python endpoint? No server → JS can't run Python directly)
- **Resolution**: Embedding viz becomes a **precomputed section** like other charts. On-demand query feature requires either:
  - A: Simple Python CGI script served by `http.server` (adds `--cgi` flag) — lightest server option
  - B: All 5 views precomputed, search is client-side filter over pre-loaded coords
  - **Choose B**: precompute all 5 Plotly divs, save as HTML snippets, embed in Jinja2. Search filters `embedding_coords.json` in-browser (loaded via `<script>` tag with inline JSON).

**New file**: `dashboard/templates/embedding_viz.html` — Jinja2 partial included by `dashboard.html`
- Tab bar: Global Map | Response Patterns | Temporal Drift | Topic Clusters | Semantic Search
- Each tab = Plotly div
- Semantic search tab: text input + results list (filters coords JSON client-side, highlights nearest neighbors)

**Modified**: `dashboard/scripts/generate_dashboard.py`
- After generating rule-based viz, run `generate_embedding_viz.py` as subprocess (unless `--skip-embedding-viz`)
- Pass Plotly div paths to template context

**Modified**: `dashboard/templates/dashboard.html`
- Add `{% include 'embedding_viz.html' %}` section before LLM Insights
- Load `embedding_coords.json` as inline `<script>` for client-side search

---

### 6. Relationship Tagging (`feat/relationship-tagging`)
**Problem**: Conversations have no relationship metadata (friend, family, work, etc.).

**Design**:
```
src/tag/
  tag_relationships.py    ← rule-based + optional LLM
```

**Two-pass approach**:
1. **Rule-based**: Keyword heuristics per conversation (mentions of "mom"/"dad" → family, "meeting"/"deadline" → work, etc.)
2. **LLM refinement**: For conversations that pass a message-count threshold, ask Llama 3.1: "Classify this relationship: family, close_friend, acquaintance, work, romantic, other."

**Output**: New field `relationship` on each chunk, stored in ChromaDB metadata, used for dashboard filtering.

---

### 7. Style Curation Tools (`feat/style-curation-tools`)
**Problem**: `config/style_examples.md` needs ~50 manually curated examples. No tooling to help.

**Design**:
```
src/curate/
  suggest_examples.py     ← uses retrieval to find "representative" messages
  validate_examples.py    ← checks format, dedup, coverage
```

**Workflow**:
1. `suggest_examples.py` queries ChromaDB for diverse message clusters, outputs candidate examples
2. User reviews, edits, moves to `style_examples.md`
3. `validate_examples.py` runs on commit to ensure format consistency

---

### 8. GUI Draft Interface (`feat/gui-draft-interface`)
**Problem**: Current interface is CLI only (`retrieve.py | generate.py`).

**Design**: Single-page HTML app in `dashboard/draft.html`
```
dashboard/
  draft.html              ← standalone draft interface
  static/js/draft.js       ← fetch context, call generate, display draft
```

**Flow**:
1. User types incoming message + selects recipient
2. JS loads static style examples (embedded in page)
3. JS calls `python src/retrieve/retrieve.py --query "..."  --json` via... browser can't call Python.
4. **Resolution**: Serve via Python CGI or use a tiny Flask/FastAPI server (breaks "no server" rule) OR precompute a "draft context cache" and serve as static JSON that the draft page loads + filters client-side.
5. **Best approach for now**: CLI stays primary. Draft HTML page is a "demo viewer" that shows pre-generated drafts from a JSON file. Real drafting still CLI.

**File**: `dashboard/templates/draft.html` — Jinja2 partial showing sample drafts.
**Script**: `dashboard/scripts/generate_drafts.py` — batch-generates drafts for recent conversations.

---

### 9. Additional Platform Support (`feat/platform-messenger`)
**Problem**: Only Instagram supported.

**Design**: 
```
src/ingest/
  instagram_parser.py    ← existing
  messenger_parser.py    ← Facebook Messenger JSON export
  whatsapp_parser.py     ← WhatsApp chat export (.txt)
```

Each parser outputs same normalized JSONL format (`sender_name`, `content`, `timestamp_ms`, `platform`, `conversation_id`). Downstream pipeline unchanged.

---

### 10. Incremental Embed (`feat/incremental-embed`)
**Problem**: `embed.py` re-embeds everything each run.

**Design**: 
- Track last embedded `timestamp_ms` per conversation in `data/processed/embed_state.json`
- On re-run, only embed messages with `timestamp_ms > last_embedded`
- Use ChromaDB `upsert` by chunk ID (already designed, not yet implemented)

---

## Dependency Graph
```
fix/emoji-detection ──────┐
fix/logging-migration ────┤
feat/config-system ───────┼──→ master (foundation fixes first)
feat/test-suite ──────────┘
        │
        ▼
feat/relationship-tagging
feat/incremental-embed
feat/style-curation-tools
        │
        ▼
feat/embedding-viz-integration ──→ dashboard feature complete
feat/gui-draft-interface
feat/platform-messenger
```

## Order of Execution
1. **Config system** — every other branch depends on it
2. **Logging migration** — improves debugging for all subsequent work
3. **Emoji detection fix** — one-line bug fix, quick win
4. **Test suite** — safety net before further feature work
5. **Embedding viz integration** — completes dashboard
6. **Relationship tagging** — enriches metadata
7. **Style curation tools** — improves generation quality
8. **Incremental embed** — performance for large datasets
9. **GUI draft interface** — UX polish
10. **Additional platforms** — scope expansion

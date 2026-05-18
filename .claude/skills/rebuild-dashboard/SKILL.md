---
name: rebuild-dashboard
description: "Full rebuild of PersonalDB dashboard: LLM features + embedding viz + render index.html"
---

# Rebuild Dashboard

Complete dashboard rebuild pipeline. Runs all three stages and writes `dashboard/index.html`.

## Pipeline Stages

| Stage | Script | Output | Slow? |
|-------|--------|--------|-------|
| 1. LLM Features | `dashboard/scripts/run_llm_features.py` | `dashboard/llm_cache/*.json` | Yes (Ollama calls) |
| 2. Embedding Viz | `dashboard/scripts/generate_embedding_viz.py` | `dashboard/data/*.json`, `dashboard/data/*.html` | Medium (UMAP fit) |
| 3. Dashboard Render | `dashboard/scripts/generate_dashboard.py` | `dashboard/index.html` | Fast |

## Execution

Run stages in order. Each stage depends on the previous stage's outputs. Always activate the virtual environment first if `.venv` exists.

### Prerequisites check

Before running, verify:
- `.venv/Scripts/activate` or equivalent venv exists
- `ollama` is running (for LLM features and embedding model)
- ChromaDB at `data/chroma/` has embeddings
- `data/processed/messages.jsonl` exists

### Stage 1: LLM Features (skippable)

```bash
python dashboard/scripts/run_llm_features.py
```

Flags: `--force` to regenerate all caches, `--n-clusters N` for topic count.

If user says `--skip-llm`, skip this stage. Stage 3 will render without LLM sections.

### Stage 2: Embedding Visualization

```bash
python dashboard/scripts/generate_embedding_viz.py
```

Flags: `--force` to re-fit UMAP reducer.

### Stage 3: Dashboard Render

```bash
python dashboard/scripts/generate_dashboard.py
```

With skip-llm:
```bash
python dashboard/scripts/generate_dashboard.py --skip-llm
```

## Post-Build

After `index.html` is written, `dashboard/server.py` can serve it:
```bash
python dashboard/server.py
```

## Report

After rebuild, summarize:
- Each stage: success/failure/skipped
- Output file size and line count for `dashboard/index.html`
- Any errors with exact traceback excerpts
- Total time elapsed

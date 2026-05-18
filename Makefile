# PersonalDB — Dependency-driven build
#
# Usage:
#   make dashboard     Build everything needed, render dashboard
#   make serve         Start dashboard server
#   make clean         Remove all generated artifacts
#
# Each target only rebuilds if its source dependencies changed.

.PHONY: all ingest preprocess embed features viz dashboard serve clean help

DATA := data/processed
CACHE := dashboard/llm_cache
VIZ_DATA := dashboard/data
CHARTS := $(VIZ_DATA)/charts
CLI := python -m personaldb.cli

all: dashboard

# ── Data pipeline ─────────────────────────────────

$(DATA)/messages.jsonl:
	@echo "messages.jsonl not found."
	@echo "Run: make ingest EXPORT_ROOT=data/raw/<your_export> ME=<your_name>"

$(DATA)/chunks.json: $(DATA)/messages.jsonl
	$(CLI) preprocess

data/chroma/: $(DATA)/chunks.json
	$(CLI) embed

# ── LLM features ─────────────────────────────────

$(CACHE)/conversation_summaries.json: $(DATA)/messages.jsonl
	$(CLI) features

# ── Embedding visualization ──────────────────────

$(VIZ_DATA)/umap_2d_reducer.pkl: data/chroma/
	$(CLI) viz

# ── Dashboard artifacts ──────────────────────────

$(CHARTS)/.built: $(DATA)/messages.jsonl
	$(CLI) dashboard build-charts
	@touch $(CHARTS)/.built

dashboard/index.html: $(CHARTS)/.built $(CACHE)/conversation_summaries.json $(VIZ_DATA)/umap_2d_reducer.pkl
	$(CLI) dashboard build

# ── User-facing targets ──────────────────────────

ingest:
	$(CLI) ingest --export-root $(EXPORT_ROOT) --me $(ME)

preprocess: $(DATA)/chunks.json

embed: data/chroma/

features: $(CACHE)/conversation_summaries.json

viz: $(VIZ_DATA)/umap_2d_reducer.pkl

dashboard: dashboard/index.html

serve:
	$(CLI) dashboard serve

# ── Maintenance ──────────────────────────────────

clean:
	rm -rf $(CACHE)/*
	rm -rf $(CHARTS)/*
	rm -f $(VIZ_DATA)/umap_*.pkl
	rm -f $(VIZ_DATA)/embedding_coords*.json
	rm -f $(VIZ_DATA)/plotly_*.html
	rm -f $(VIZ_DATA)/.hashes.json
	rm -f dashboard/index.html

help:
	@echo "PersonalDB Build System"
	@echo ""
	@echo "Targets:"
	@echo "  make ingest EXPORT_ROOT=<path> ME=<name>   Parse Instagram export"
	@echo "  make preprocess                              Chunk messages"
	@echo "  make embed                                   Generate embeddings"
	@echo "  make features                                Run LLM features"
	@echo "  make viz                                     Precompute embedding viz"
	@echo "  make dashboard                               Build dashboard HTML"
	@echo "  make serve                                   Start dashboard server"
	@echo "  make clean                                   Remove all generated files"
	@echo ""
	@echo "Shortcut: make dashboard  rebuilds only stale artifacts"

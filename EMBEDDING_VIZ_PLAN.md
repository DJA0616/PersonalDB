# Embedding Visualization Plan

## Problem
ChromaDB stores nomic-embed-text vectors (768-dim). Need to visualize these high-dimensional
embeddings in 2D/3D to reveal semantic patterns: how my responses cluster, which conversations
are similar, what words/phrases correlate in embedding space.

## Core Approach
Dimensionality reduction via UMAP (preserves global + local structure better than t-SNE)
→ interactive Plotly scatter plots embedded in dashboard HTML.

## Views (5 visualization modes)

### 1. Global Conversation Map
**What**: All message chunks projected to 2D, colored by sender/person.
**Reveals**: Whose conversations cluster together. Whether my replies to different people
form distinct semantic regions. Overlap between my style and others'.
**Data**: All chunk embeddings from ChromaDB `messages` collection.
**Interaction**: Hover shows chunk text. Click filters to that person.

### 2. Self-Response Pattern Map  
**What**: For messages I receive (query), plot where my replies (response) land in embedding
space. Draw arrows from query → response points.
**Reveals**: How my reply style shifts based on what was said to me. Whether certain types
of incoming messages trigger consistent reply patterns.
**Data**: Paired (incoming_message, my_reply) chunks projected together. Arrows drawn as
Plotly line traces.
**Interaction**: Click arrow shows the incoming→reply text pair.

### 3. Temporal Drift River
**What**: Embeddings plotted with time as third dimension (color gradient or animation frames).
**Reveals**: How my language/style evolved over months. Semantic drift detection.
**Data**: Chunks sorted by timestamp_ms, colored by month.
**Interaction**: Slider to filter time range. Play button to animate.

### 4. Topic Cluster Voronoi
**What**: UMAP projection with KMeans cluster boundaries (Voronoi cells). Each cluster
labeled by LLM-generated topic name.
**Reveals**: Natural topic groupings in my conversations. Boundary messages (near cluster edges)
are semantically ambiguous.
**Data**: Chunk embeddings + KMeans labels + LLM topic names.
**Interaction**: Click cluster to see representative messages. Click boundary region to see
ambiguous messages.

### 5. Word/Phrase Semantic Field
**What**: User types a word or phrase → its embedding is projected among the conversation
embeddings. Nearest neighbors highlighted with distances.
**Reveals**: What contexts I use specific words in. Semantic neighborhood of any phrase.
**Data**: Query embedding (computed on-demand) projected into existing UMAP space (use
transform, not refit).
**Interaction**: Search box. Results shown as highlighted scatter points + ranked list.

## Technical Design

### Dimensionality Reduction
- **Library**: `umap-learn` (UMAP)
- **Parameters**: n_neighbors=15, min_dist=0.1, n_components=2, metric='cosine'
- **Fit once, save**: Fit UMAP on all chunk embeddings once, save reducer as pickle
  (`dashboard/data/umap_reducer.pkl`). New query embeddings use `transform()` (no refit).
- **3D option**: n_components=3 for optional 3D view (Plotly supports WebGL 3D scatter)

### Interactive Plotting
- **Library**: `plotly` (offline mode, generates self-contained HTML div)
- **Export**: Each plot saved as standalone HTML snippet, embedded via Jinja2 `{{ plot_div | safe }}`
- **No server needed**: Plotly JavaScript bundled in the HTML (include from CDN or local)
- **Color palette**: Use design system colors (steel-blue #7eb8d4, sage #a0d4b0, dim #555555)

### Data Pipeline
```
ChromaDB collection → get(all_embeddings + metadata)
                     → UMAP fit_transform → 2D coords
                     → save coords + metadata → dashboard/data/embedding_coords.json
                     → Plotly generates HTML divs → Jinja2 embeds in dashboard
```

### File Structure
```
dashboard/
  scripts/
    generate_embedding_viz.py    # Main script: load embeddings, reduce, plot
  data/
    umap_reducer.pkl              # Fitted UMAP model (for transform queries)
    embedding_coords.json         # Precomputed 2D coords for all chunks
  templates/
    embedding_viz.html            # Jinja2 partial with Plotly divs
  static/
    js/
      embedding_viz.js             # Interactive controls (search, filter, animate)
```

### generate_embedding_viz.py Design
- **Input**: ChromaDB collection path, normalized messages JSONL
- **Output**: `embedding_coords.json` + Plotly HTML divs + updated dashboard section
- **CLI args**: `--chroma-path`, `--input`, `--output-dir`, `--force` (refit UMAP)
- **Steps**:
  1. Load all embeddings + metadata from ChromaDB
  2. Fit or load UMAP reducer
  3. Transform to 2D/3D coordinates
  4. Generate each Plotly figure
  5. Save coords JSON + figures as HTML snippets
  6. Print embedding for on-demand queries via stdin

### On-Demand Query Interface
- `generate_embedding_viz.py --query "phrase"` computes embedding via Ollama,
  transforms into existing UMAP space, returns nearest neighbors + 2D position.
- Used by dashboard JS search box (or regenerated HTML with query result section).

### Integration with generate_dashboard.py
- `generate_dashboard.py` calls `generate_embedding_viz.py` as subprocess
  (or imports its functions) to get Plotly divs.
- Embedding section in dashboard.html: tabbed interface (5 tabs for 5 views).
- If embeddings not computed yet, show "Run generate_embedding_viz.py to enable
  semantic visualizations."

## Dependencies to Add
- `umap-learn`
- `plotly`
- `scikit-learn` (already needed for topic clustering)
- `numpy` (already needed)

## Build Phase (for embedding viz)
1. Install new deps: `umap-learn`, `plotly`
2. Write `generate_embedding_viz.py` (UMAP + Plotly generation)
3. Write `embedding_viz.js` (interactive controls)
4. Write `embedding_viz.html` Jinja2 partial
5. Integrate into `generate_dashboard.py` (add embedding section)
6. Test with sample embeddings
7. Push

## Edge Cases & Performance
- **Empty ChromaDB**: Graceful message, skip section.
- **< 50 chunks**: UMAP needs sufficient points; fallback to PCA for small datasets.
- **Large datasets (>10K chunks)**: Use UMAP `transform` mode with subset fitting,
  or sample representative points.
- **Ollama offline**: Skip on-demand query feature, show cached results only.
- **Browser memory**: Plotly with >5K points can lag. Use WebGL renderer,
  scattergl trace type, or random sampling for display.

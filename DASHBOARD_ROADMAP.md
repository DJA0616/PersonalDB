Dashboard architecture roadmap.

Folder structure:
dashboard/
  static/
    css/
      theme.css
    js/
      utils.js
  templates/
    dashboard.html
  data/
    cached_aggregates.json
  llm_cache/
    conversation_summaries.json
    topic_clusters.json
    sentiment_trends.json
  scripts/
    generate_rulebased.py
    run_llm_features.py
    generate_dashboard.py
  index.html

Python libraries per visualization:
Word cloud: wordcloud
Pie chart bar chart histogram timeline: matplotlib (convert to base64 embed) or plotly (offline HTML)
Noise filter report chunk size histogram: matplotlib
Design theme: CSS via provided theme file

Data flow:
1. Load normalized JSON from data/processed/instagram_normalized.json
2. Compute rule-based aggregates (word counts per person message volume per platform avg length over time hourly daily monthly activity noise filter stats chunk sizes)
3. Generate chart images (matplotlib save to base64 strings) or HTML div (plotly)
4. For LLM features:
   a. Per-conversation summary: group by conversation send prompt to Ollama Llama 3.1 8B cache result
   b. Topic clustering: extract text from all conversations embed via nomic-embed-text (or reuse existing embeddings) run KMeans clustering assign topic labels
   c. Sentiment trend over time per person: for each person compute sentiment per message via Ollama aggregate by time window
5. Combine rule-based visualizations (fast) and LLM features (slower) into dashboard HTML
6. Apply design theme via CSS
7. Output single index.html (or separate files if using iframes for LLM parts)

LLM integration nonblocking approach:
- Generate rule-based dashboard first show immediately
- Run LLM features in background subprocess
- When LLM complete update llm_cache JSON files
- Dashboard JavaScript periodically fetches llm_cache JSON (if served via simple HTTP dev server) OR
- Alternative: regenerate entire dashboard after LLM complete (blocking during generation but static output nonblocking)
Given no server requirement choose static regeneration: run full pipeline rulebased then LLM then output final HTML
User waits for generation then views dashboard

Build phases:
1. Scaffold dashboard/ folder structure
2. Install dependencies: wordcloud matplotlib ollama (for LLM) jinja2 (if templating)
3. Implement rulebased visualization modules (charts wordcloud histograms)
4. Implement LLM feature modules (summarization topic clustering sentiment via Ollama)
5. Create main generate_dashboard.py script that loads data runs rulebased runs LLM combines output applies theme writes index.html
6. Apply user provided design theme to dashboard CSS
7. Test with sample data verify offline functionality
8. Document usage: python dashboard/scripts/generate_dashboard.py then open dashboard/index.html
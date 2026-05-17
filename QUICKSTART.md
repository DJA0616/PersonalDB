# PersonalDB Quickstart

## Prerequisites
- [Ollama](https://ollama.com) installed and running
- Python 3.8+
- Git (optional, for version control)

## Steps

### 1. Install Ollama models
```powershell
ollama pull nomic-embed-text
ollama pull llama3.1:8b
```

### 2. Install Python dependencies
```powershell
pip install -r requirements.txt
```

### 3. Prepare test data (optional but recommended for first run)
Create a minimal Instagram export structure under `data/raw/`:
```
data/raw/
└── your_instagram_activity/
    └── messages/
        └── inbox/
            └── conv1/
                ├── message_1.json
                └── message_2.json
```

Example `message_1.json`:
```json
{
  "participants": [
    {"name": "Friend"},
    {"name": "Me"}
  ],
  "messages": [
    {
      "sender_name": "Me",
      "timestamp_ms": 1234567890,
      "content": "Hey, how are you?"
    },
    {
      "sender_name": "Friend",
      "timestamp_ms": 1234567891,
      "content": "I'm good, thanks!"
    }
  ]
}
```

### 4. Run the pipeline
```powershell
# Parse Instagram export (adjust --me to your name in the export)
python src/ingest/instagram_parser.py --export-root data/raw --me Me --out data/processed/messages.jsonl

# Preprocess (filter, tag, chunk)
python src/preprocess/preprocess.py --input data/processed/messages.jsonl --out data/processed/chunks.json

# Embed and store in ChromaDB
python src/embed/embed.py --input data/processed/chunks.json

# Test retrieval (example query)
python src/retrieve/retrieve.py --query "How to respond to a friend asking how you are?" --top-k 3

# Test generation (using the retrieved context)
# First, capture the retrieval output to a file or pipe it
python src/retrieve/retrieve.py --query "How to respond to a friend asking how you are?" --top-k 3 > context.json
# Then generate
type context.json | python src/generate/generate.py --context-stdin --prompt "Friend just asked how I am. Draft a casual reply."
```

## Notes
- The `data/` folder is ignored by git (see `.gitignore`).
- For real use, place your Instagram export in `data/raw/` (but keep it backed up and never commit).
- Adjust model names in scripts if you use different ones.
- The static style examples file (`config/style_examples.md`) should be curated manually (~50 examples of your tone).

## Troubleshooting
- If Ollama is not running, start it with `ollama serve` in a separate terminal.
- Ensure the Python scripts have execute permissions if needed (on Windows, just run with `python`).
- Check ChromaDB persistence: data is stored in `data/chroma/` by default.
"""
Data access layer for PersonalDB.

Single Store class wraps all file I/O. Every script loads and saves
data through the Store — never by direct file path manipulation.

Usage:
    from personaldb.store import Store
    store = Store()
    messages = store.get_messages()
    chunks = store.get_chunks()
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from personaldb.config import get_config


class Store:
    """Central access point for all project data artifacts."""

    def __init__(self, cfg: Optional[Dict[str, Any]] = None):
        self._cfg = cfg or get_config()
        self._root = Path(__file__).resolve().parent.parent.parent
        self._messages_cache: Optional[List[Dict[str, Any]]] = None
        self._chunks_cache: Optional[List[Dict[str, Any]]] = None
        self._chroma_client = None

    # ── Path properties ──────────────────────────────

    @property
    def messages_path(self) -> Path:
        return self._root / self._cfg["paths"]["data_processed"] / "messages.jsonl"

    @property
    def chunks_path(self) -> Path:
        return self._root / self._cfg["paths"]["data_processed"] / "chunks.json"

    @property
    def chroma_path(self) -> Path:
        return self._root / self._cfg["paths"]["chroma"]

    @property
    def llm_cache_dir(self) -> Path:
        return self._root / self._cfg["dashboard"]["llm_cache_dir"]

    @property
    def dashboard_data_dir(self) -> Path:
        return self._root / self._cfg["dashboard"]["plotly_output_dir"]

    @property
    def style_examples_path(self) -> Path:
        return self._root / self._cfg["paths"]["style_examples"]

    @property
    def charts_dir(self) -> Path:
        return self.dashboard_data_dir / "charts"

    @property
    def template_dir(self) -> Path:
        return self._root / self._cfg["dashboard"]["template_dir"]

    # ── Read methods ─────────────────────────────────

    def get_messages(self, reload: bool = False) -> List[Dict[str, Any]]:
        """Load normalized messages from JSONL. Cached in memory after first load."""
        if self._messages_cache is not None and not reload:
            return self._messages_cache

        path = self.messages_path
        if not path.exists():
            raise FileNotFoundError(
                f"Messages file not found: {path}\n"
                "Run: python -m personaldb.ingest.instagram_parser --export-root <path> --me <name>"
            )

        records: List[Dict[str, Any]] = []
        with open(path, "r", encoding="utf-8") as fh:
            if path.suffix == ".jsonl":
                for line in fh:
                    line = line.strip()
                    if line:
                        records.append(json.loads(line))
            else:
                data = json.load(fh)
                if isinstance(data, list):
                    records = data
                elif isinstance(data, dict):
                    for key in ("messages", "records", "data"):
                        val = data.get(key)
                        if isinstance(val, list):
                            records = val
                            break
                    else:
                        for val in data.values():
                            if isinstance(val, list):
                                records = val
                                break

        # Normalize field names to canonical form
        for msg in records:
            if "content" not in msg:
                msg["content"] = msg.get("text", "")
            if "sender_name" not in msg:
                msg["sender_name"] = msg.get("sender", "Unknown")
            if "platform" not in msg:
                msg["platform"] = msg.get("platform", "instagram")

        self._messages_cache = records
        return records

    def get_chunks(self, reload: bool = False) -> Optional[List[Dict[str, Any]]]:
        """Load preprocessed chunks. Returns None if chunks.json doesn't exist."""
        if self._chunks_cache is not None and not reload:
            return self._chunks_cache

        path = self.chunks_path
        if not path.exists():
            return None

        with open(path, "r", encoding="utf-8") as fh:
            self._chunks_cache = json.load(fh)
        return self._chunks_cache

    def get_chroma_client(self):
        """Return a singleton ChromaDB PersistentClient."""
        if self._chroma_client is None:
            import chromadb
            self._chroma_client = chromadb.PersistentClient(path=str(self.chroma_path))
        return self._chroma_client

    def get_chroma_collection(self):
        """Return the configured ChromaDB collection."""
        client = self.get_chroma_client()
        name = self._cfg["embed"]["collection_name"]
        return client.get_collection(name=name)

    def get_llm_cache(self, name: str) -> Optional[Any]:
        """Load a cached LLM result JSON file. Returns None if missing."""
        path = self.llm_cache_dir / name
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError):
            return None

    # ── Write methods ────────────────────────────────

    def save_llm_cache(self, name: str, data: Any) -> None:
        """Persist data as JSON to the LLM cache directory."""
        self.llm_cache_dir.mkdir(parents=True, exist_ok=True)
        path = self.llm_cache_dir / name
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)

    def save_chart(self, name: str, image_base64: str) -> Path:
        """Save a base64 chart image to dashboard/data/charts/<name>.png."""
        import base64
        self.charts_dir.mkdir(parents=True, exist_ok=True)
        path = self.charts_dir / f"{name}.png"
        with open(path, "wb") as fh:
            fh.write(base64.b64decode(image_base64))
        return path

    def save_dashboard_json(self, name: str, data: Any) -> Path:
        """Save a JSON artifact to dashboard/data/<name>.json."""
        self.dashboard_data_dir.mkdir(parents=True, exist_ok=True)
        path = self.dashboard_data_dir / f"{name}.json"
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        return path

    def load_dashboard_json(self, name: str) -> Optional[Any]:
        """Load a JSON artifact from dashboard/data/<name>.json."""
        path = self.dashboard_data_dir / f"{name}.json"
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def load_chart_base64(self, name: str) -> Optional[str]:
        """Load a saved chart PNG as a base64 string."""
        import base64
        path = self.charts_dir / f"{name}.png"
        if not path.exists():
            return None
        with open(path, "rb") as fh:
            return base64.b64encode(fh.read()).decode("ascii")

    # ── Cache invalidation ───────────────────────────

    def _hashes_path(self) -> Path:
        return self.dashboard_data_dir / ".hashes.json"

    def _load_hashes(self) -> dict:
        path = self._hashes_path()
        if path.exists():
            try:
                return json.loads(path.read_text())
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _save_hashes(self, hashes: dict) -> None:
        self.dashboard_data_dir.mkdir(parents=True, exist_ok=True)
        self._hashes_path().write_text(json.dumps(hashes, indent=2))

    def _resolve_source(self, name: str) -> Path:
        """Resolve a symbolic source name to an actual file path."""
        mapping = {
            "messages": self.messages_path,
            "chunks": self.chunks_path,
            "chroma": self.chroma_path / "chroma.sqlite3",
            "conversation_summaries": self.llm_cache_dir / "conversation_summaries.json",
            "topic_clusters": self.llm_cache_dir / "topic_clusters.json",
            "sentiment_trends": self.llm_cache_dir / "sentiment_trends.json",
            "personality_analysis": self.llm_cache_dir / "personality_analysis.json",
            "embedding_coords": self.dashboard_data_dir / "embedding_coords_2d.json",
            "embedding_metadata": self.dashboard_data_dir / "embedding_metadata.json",
            "embedding_timeline": self.dashboard_data_dir / "embedding_timeline.json",
        }
        if name in mapping:
            return mapping[name]
        return Path(name)

    @staticmethod
    def _sha256(path: Path) -> str:
        """Compute SHA256 hex digest of a file."""
        import hashlib
        if not path.exists():
            return "missing"
        sha = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha.update(chunk)
        return sha.hexdigest()

    def is_stale(self, artifact_name: str, *source_names: str) -> bool:
        """Return True if any source file changed since artifact was built.

        source_names are symbolic (e.g. "messages", "chunks") or file paths.
        """
        stored = self._load_hashes()

        for src_name in source_names:
            src_path = self._resolve_source(src_name)
            current_hash = self._sha256(src_path)
            cache_key = f"{src_name}->{artifact_name}"
            if stored.get(cache_key) != current_hash:
                return True

        return False

    def mark_fresh(self, artifact_name: str, *source_names: str) -> None:
        """Record current hashes after successful build."""
        stored = self._load_hashes()

        for src_name in source_names:
            src_path = self._resolve_source(src_name)
            current_hash = self._sha256(src_path)
            cache_key = f"{src_name}->{artifact_name}"
            stored[cache_key] = current_hash

        self._save_hashes(stored)

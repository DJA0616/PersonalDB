"""
BM25 keyword search index for hybrid retrieval.

No external dependencies — pure Python stdlib.
"""

import re
import math
from collections import Counter
from typing import List, Tuple, Dict


class BM25Index:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self._docs: List[List[str]] = []
        self._doc_len: List[int] = []
        self._avgdl: float = 0.0
        self._df: Dict[str, int] = {}
        self._idf: Dict[str, float] = {}
        self._N: int = 0

    def _tokenize(self, text: str) -> List[str]:
        return [t.lower() for t in re.split(r'\W+', text) if t]

    def index(self, documents: List[str]) -> None:
        self._docs = [self._tokenize(d) for d in documents]
        self._doc_len = [len(d) for d in self._docs]
        self._N = len(self._docs)
        self._avgdl = sum(self._doc_len) / max(self._N, 1) if self._N > 0 else 1.0

        self._df = {}
        for doc in self._docs:
            for term in set(doc):
                self._df[term] = self._df.get(term, 0) + 1

        for term, df in self._df.items():
            self._idf[term] = math.log((self._N - df + 0.5) / (df + 0.5) + 1)

    def search(self, query: str, top_k: int) -> List[Tuple[int, float]]:
        if self._N == 0:
            return []
        query_terms = self._tokenize(query)
        scores = []
        for idx, doc in enumerate(self._docs):
            score = 0.0
            doc_len = self._doc_len[idx]
            tf_counter = Counter(doc)
            for term in query_terms:
                if term not in self._idf:
                    continue
                tf = tf_counter.get(term, 0)
                if tf == 0:
                    continue
                idf = self._idf[term]
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / max(self._avgdl, 1.0))
                score += idf * numerator / denominator
            if score > 0:
                scores.append((idx, score))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

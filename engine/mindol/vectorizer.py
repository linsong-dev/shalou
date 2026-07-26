"""mindol.vectorizer - n-gram hash vectorizer"""
from __future__ import annotations
import hashlib, re
import numpy as np

class SimpleVectorizer:
    def __init__(self, dim: int = 256):
        self.dim = dim
    def _hash_ngram(self, ngram: str) -> int:
        return int(hashlib.sha256(ngram.encode("utf-8")).hexdigest()[:8], 16)
    def embed(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dim, dtype=np.float32)
        if not text.strip(): return vec
        features = {}; text_lower = text.lower()
        for ch in text_lower:
            if ch.strip():
                h = self._hash_ngram(f"c_{ch}"); features[h % self.dim] = features.get(h % self.dim, 0) + 0.5
        for i in range(len(text_lower) - 1):
            bg = text_lower[i:i+2]
            if bg.strip():
                h = self._hash_ngram(f"b_{bg}"); features[h % self.dim] = features.get(h % self.dim, 0) + 1.0
        for i in range(len(text_lower) - 2):
            tg = text_lower[i:i+3]
            if tg.strip():
                h = self._hash_ngram(f"t_{tg}"); features[h % self.dim] = features.get(h % self.dim, 0) + 1.5
        words = re.findall(r"[\w]+", text_lower)
        for w in words:
            if len(w) >= 2:
                h = self._hash_ngram(f"w_{w}"); features[h % self.dim] = features.get(h % self.dim, 0) + 2.0
        for idx, val in features.items(): vec[idx] = val
        norm = np.linalg.norm(vec)
        if norm > 0: vec = vec / norm
        return vec

    def calc_similarity(self, text_a: str, text_b: str) -> float:
        """增强相似度: Jaccard 多维度 + cosine 混合
        解决 n-gram hash 对中文短文本相似度低的问题。
        权重: char_jaccard*0.35 + bigram_jaccard*0.35 + cosine*0.30
        """
        if not text_a.strip() or not text_b.strip():
            return 0.0

        # 1. 字符集 Jaccard
        set_a, set_b = set(text_a), set(text_b)
        char_j = 0.0
        if set_a and set_b:
            char_j = len(set_a & set_b) / len(set_a | set_b)

        # 2. 双字 Jaccard
        big_a = set(text_a[i:i+2] for i in range(len(text_a)-1))
        big_b = set(text_b[i:i+2] for i in range(len(text_b)-1))
        bigram_j = 0.0
        if big_a and big_b:
            bigram_j = len(big_a & big_b) / len(big_a | big_b)

        # 3. 原 cosine
        va = self.embed(text_a)
        vb = self.embed(text_b)
        norm_a = np.linalg.norm(va)
        norm_b = np.linalg.norm(vb)
        cos = 0.0
        if norm_a > 0 and norm_b > 0:
            cos = float(np.dot(va, vb) / (norm_a * norm_b))
        cos = max(0.0, cos)  # 截断负值

        # 加权混合
        return char_j * 0.35 + bigram_j * 0.35 + cos * 0.30

        def embedding_dim(self) -> int: return self.dim

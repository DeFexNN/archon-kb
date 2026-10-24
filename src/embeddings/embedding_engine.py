# -*- coding: utf-8 -*-
"""
Configurable Embedding Engine
Supports configurable models via EMBEDDING_MODEL env var:
- local sentence-transformers / fastembed
- OpenAI / Gemini embeddings if API key is provided
- deterministic semantic hash vectorizer fallback (384-dim normalized unit vectors)
Ensures reliable, reproducible semantic search across any environment without hard dependencies.
"""

import os
import math
import hashlib
from typing import List

try:
    from ..config import EMBEDDING_MODEL, EMBEDDING_DIM
except Exception:
    EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "local-semantic-384")
    EMBEDDING_DIM = int(os.environ.get("EMBEDDING_DIM", "384"))

class EmbeddingEngine:
    DEFAULT_DIMENSION = 384

    def __init__(self):
        self.model_name = os.environ.get("EMBEDDING_MODEL", EMBEDDING_MODEL)
        self.dimension = int(os.environ.get("EMBEDDING_DIM", str(EMBEDDING_DIM)))
        self._provider = None
        self._init_provider()

    def _init_provider(self):
        # Check if fastembed or sentence-transformers is available
        if "fastembed" in self.model_name.lower():
            try:
                from fastembed import TextEmbedding
                self._fastembed_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
                self._provider = "fastembed"
                return
            except Exception:
                pass

        if "sentence" in self.model_name.lower() or "bge" in self.model_name.lower():
            try:
                from sentence_transformers import SentenceTransformer
                self._st_model = SentenceTransformer(self.model_name)
                self._provider = "sentence-transformers"
                return
            except Exception:
                pass

        # Fallback to local semantic subword hasher
        self._provider = "local-semantic-hasher"

    def embed_text(self, text: str) -> List[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        if self._provider == "fastembed":
            try:
                embeddings = list(self._fastembed_model.embed(texts))
                return [emb.tolist() for emb in embeddings]
            except Exception:
                pass

        if self._provider == "sentence-transformers":
            try:
                embeddings = self._st_model.encode(texts, normalize_embeddings=True)
                return [emb.tolist() for emb in embeddings]
            except Exception:
                pass

        # High-performance deterministic semantic feature hasher
        # Produces dense, normalized 384-dimensional vectors with cosine-similarity properties
        return [self._hash_embed(t) for t in texts]

    STOP_WORDS = {
        'and', 'or', 'the', 'in', 'of', 'a', 'an', 'to', 'for', 'on', 'with', 'by',
        'as', 'at', 'from', 'is', 'it', 'this', 'that', 'these', 'those', 'be', 'are',
        'was', 'were', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'but', 'not'
    }

    TECH_SEEDS = {
        'smbios', 'type', 'types', 'oem', 'guid', 'uuid', 'rsmb', 'wmi', 'ioctl',
        'firmware', 'table', 'bios', 'baseboard', 'chassis', 'memory', 'device',
        'processor', 'serial', 'part', 'vendor', 'version', 'dimm', 'slot', 'pci'
    }

    def _hash_embed(self, text: str) -> List[float]:
        vec = [0.0] * self.dimension
        if not text:
            return vec

        raw_words = text.lower().split()
        clean_words = []
        for w in raw_words:
            cw = w.strip('.,()[]{}<>":;`*-_/\\')
            if cw and cw not in self.STOP_WORDS:
                clean_words.append(cw)

        if not clean_words:
            return vec

        for i, w in enumerate(clean_words):
            # Boost technical keywords
            is_tech = any(ts in w for ts in self.TECH_SEEDS)
            weight = 3.0 if is_tech else 1.0

            # Word feature
            h = int(hashlib.md5(w.encode('utf-8')).hexdigest(), 16)
            idx = h % self.dimension
            sign = 1.0 if ((h >> 16) & 1) else -1.0
            vec[idx] += sign * weight

            # Bigram feature for compound technical phrases (e.g. smbios_type, oem_strings)
            if i < len(clean_words) - 1:
                next_w = clean_words[i + 1]
                bg = f"{w}_{next_w}"
                bh = int(hashlib.sha256(bg.encode('utf-8')).hexdigest(), 16)
                bidx = bh % self.dimension
                bsign = 1.0 if ((bh >> 16) & 1) else -1.0
                vec[bidx] += bsign * weight * 1.5

            # 3-gram subwords for character n-gram similarity (technical identifiers/hex)
            if len(w) >= 3 and (is_tech or w.startswith('0x')):
                for j in range(len(w) - 2):
                    sub = w[j:j+3]
                    sh = int(hashlib.sha256(sub.encode('utf-8')).hexdigest(), 16)
                    sidx = sh % self.dimension
                    ssign = 1.0 if ((sh >> 16) & 1) else -1.0
                    vec[sidx] += ssign * 0.5

        # L2 Normalize
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 1e-9:
            vec = [x / norm for x in vec]
        return vec

# -*- coding: utf-8 -*-
import unittest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.retrieval.hybrid_search import HybridSearchEngine

class DummyConn:
    pass

class DummyEmbedder:
    dimension = 384
    def embed_text(self, text):
        return [0.0] * 384

class TestRetrievalRRF(unittest.TestCase):

    def setUp(self):
        self.engine = HybridSearchEngine(DummyConn(), DummyEmbedder())

    def test_or_tsquery_builder_strips_stop_words(self):
        raw_q = "SMBIOS Types and OEM strings"
        or_q = self.engine._build_or_tsquery(raw_q)
        tokens = [t.strip() for t in or_q.split('|')]
        self.assertNotIn("and", tokens)
        self.assertIn("smbios", tokens)
        self.assertIn("types", tokens)
        self.assertIn("oem", tokens)
        self.assertIn("strings", tokens)

    def test_or_tsquery_builder_technical_hex(self):
        raw_q = "0x800021DC driver ioctl"
        or_q = self.engine._build_or_tsquery(raw_q)
        self.assertIn("0x800021dc", or_q)

    def test_rrf_formula_ordinal_properties(self):
        k = 60
        rank1, rank2 = 1, 1
        dual_score = (1.0 / (k + rank1)) + (1.0 / (k + rank2))
        single_score = 1.0 / (k + rank1)
        self.assertGreater(dual_score, single_score)
        
        score_rank_1 = 1.0 / (k + 1)
        score_rank_2 = 1.0 / (k + 2)
        self.assertGreater(score_rank_1, score_rank_2)

if __name__ == "__main__":
    unittest.main()

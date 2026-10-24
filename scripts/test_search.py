# -*- coding: utf-8 -*-
"""
Interactive / CLI Search Testing Script for Archon-KB
"""

import os
import sys
import argparse
import json

kb_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if kb_root not in sys.path:
    sys.path.insert(0, kb_root)

from src.api.llm_tools import LLMKnowledgeBase

def main():
    parser = argparse.ArgumentParser(description="Query Archon-KB from terminal")
    parser.add_argument("query", nargs="?", default="IOCTL", help="Search query")
    parser.add_argument("--limit", type=int, default=3, help="Max results")
    args = parser.parse_args()

    print(f"[*] Querying Archon-KB for: '{args.query}' (limit={args.limit})...\n")
    kb = LLMKnowledgeBase()
    results = kb.search(args.query, limit=args.limit)

    print(json.dumps(results, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()

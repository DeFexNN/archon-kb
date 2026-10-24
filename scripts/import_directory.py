# -*- coding: utf-8 -*-
"""
Directory Ingestion Script
Recursively discovers and imports all Markdown (.md, .markdown) files into Archon-KB.
"""

import os
import sys
import argparse

kb_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if kb_root not in sys.path:
    sys.path.insert(0, kb_root)

from scripts.import_file import import_file

def import_directory(dir_path: str):
    abs_dir = os.path.abspath(dir_path)
    if not os.path.isdir(abs_dir):
        print(f"[-] Directory not found: {abs_dir}")
        return

    md_files = []
    for root, _, files in os.walk(abs_dir):
        for f in files:
            if f.lower().endswith(('.md', '.markdown')):
                md_files.append(os.path.join(root, f))

    print(f"[*] Found {len(md_files)} Markdown files in: {abs_dir}")
    if not md_files:
        return

    success_count = 0
    fail_count = 0

    for idx, f in enumerate(md_files, start=1):
        print(f"\n[{idx}/{len(md_files)}] Processing: {os.path.basename(f)}")
        try:
            if import_file(f):
                success_count += 1
            else:
                fail_count += 1
        except Exception as e:
            print(f"[-] Failed to import {f}: {e}")
            fail_count += 1

    print("\n" + "=" * 70)
    print(f"[+] Ingestion complete. Success: {success_count}, Failed: {fail_count}")
    print("=" * 70)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest directory of Markdown files into Archon-KB")
    parser.add_argument("directory", help="Path to directory containing markdown files")
    args = parser.parse_args()
    import_directory(args.directory)

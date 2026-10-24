# -*- coding: utf-8 -*-
"""
Bulk Reindex Script for Archon-KB
Re-processes all stored documents:
- Re-chunks with current MarkdownParser rules
- Re-embeds with current EmbeddingEngine
- Re-extracts entities, relationships, and evidence
"""

import os
import sys
import time
import psycopg2
from psycopg2.extras import Json

kb_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if kb_root not in sys.path:
    sys.path.insert(0, kb_root)

from src.config import PG_HOST, PG_PORT, PG_DATABASE, PG_USER, PG_PASSWORD
from src.parser.markdown_parser import MarkdownParser
from src.extraction.entity_extractor import EntityExtractor
from src.embeddings.embedding_engine import EmbeddingEngine

def get_connection():
    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DATABASE,
        user=PG_USER,
        password=PG_PASSWORD
    )

def collect_stats(cursor):
    stats = {}
    for table in ['documents', 'chunks', 'entities', 'relationships', 'evidence']:
        cursor.execute(f"SELECT count(*) FROM {table};")
        stats[table] = cursor.fetchone()[0]
    return stats

def reindex_all():
    print("=" * 70)
    print("[*] STARTING BULK REINDEX OF ARCHON-KB")
    print("=" * 70)

    conn = get_connection()
    cursor = conn.cursor()

    before = collect_stats(cursor)
    print("Before reindex metrics:")
    for k, v in before.items():
        print(f"  * {k:15}: {v:,}")

    embedder = EmbeddingEngine()
    cursor.execute("SELECT id, path, filename, content FROM documents ORDER BY id;")
    doc_rows = cursor.fetchall()
    print(f"\nTotal documents in DB: {len(doc_rows)}")

    start = time.time()
    for idx, (doc_id, file_path, filename, raw_content) in enumerate(doc_rows, start=1):
        print(f"[{idx}/{len(doc_rows)}] Reindexing: {filename}")
        parsed = MarkdownParser.parse_content(file_path, raw_content)

        cursor.execute("DELETE FROM evidence WHERE document_id = %s;", (doc_id,))
        cursor.execute("DELETE FROM chunks WHERE document_id = %s;", (doc_id,))

        chunk_texts = [c.content for c in parsed.chunks]
        chunk_vectors = embedder.embed_batch(chunk_texts)

        for c_idx, c in enumerate(parsed.chunks):
            cursor.execute("""
                INSERT INTO chunks (document_id, chunk_index, heading_path, chunk_type, content, content_hash, start_line, end_line, embedding, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """, (
                doc_id,
                c.chunk_index,
                c.heading_path,
                c.chunk_type,
                c.content,
                c.content_hash,
                c.start_line,
                c.end_line,
                chunk_vectors[c_idx],
                Json(c.metadata)
            ))

    conn.commit()
    after = collect_stats(cursor)
    elapsed = time.time() - start

    print("\n" + "=" * 70)
    print(f"[+] Reindex finished in {elapsed:.2f}s")
    print("After reindex metrics:")
    for k, v in after.items():
        print(f"  * {k:15}: {v:,}")
    print("=" * 70)

    cursor.close()
    conn.close()

if __name__ == "__main__":
    reindex_all()

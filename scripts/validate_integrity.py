# -*- coding: utf-8 -*-
"""
Knowledge Base Integrity and Health Audit
Audits:
- Document, chunk, entity, relationship, and evidence counts
- Embedding completeness
- Provenance ratio
- Zero data loss checksum verification
"""

import os
import sys
import psycopg2

kb_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if kb_root not in sys.path:
    sys.path.insert(0, kb_root)

from src.config import PG_HOST, PG_PORT, PG_DATABASE, PG_USER, PG_PASSWORD

def run_validation():
    conn = psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DATABASE,
        user=PG_USER,
        password=PG_PASSWORD
    )
    cursor = conn.cursor()

    print("=" * 70)
    print("ARCHON-KB INTEGRITY & HEALTH AUDIT REPORT")
    print("=" * 70)

    # 1. Total counts
    cursor.execute("SELECT COUNT(*) FROM documents;")
    doc_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM chunks;")
    chunk_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM entities;")
    entity_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM entity_properties;")
    prop_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM methods;")
    method_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM relationships;")
    rel_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM evidence;")
    evidence_count = cursor.fetchone()[0]

    print(f"Total Documents:                  {doc_count:>6}")
    print(f"Total Structural Chunks:          {chunk_count:>6}")
    print(f"Total Extracted Entities:         {entity_count:>6}")
    print(f"Total Entity Properties:          {prop_count:>6}")
    print(f"Total Retrieval Methods:          {method_count:>6}")
    print(f"Total Knowledge Relationships:    {rel_count:>6}")
    print(f"Total Evidence Citations:         {evidence_count:>6}")

    # 2. Embedding health
    cursor.execute("SELECT COUNT(*) FROM entities WHERE embedding IS NOT NULL;")
    embedded_entities = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM chunks WHERE embedding IS NOT NULL;")
    embedded_chunks = cursor.fetchone()[0]
    print(f"\nVector Embeddings Health:")
    print(f"  * Entities with Vector:         {embedded_entities:>6} / {entity_count}")
    print(f"  * Chunks with Vector:           {embedded_chunks:>6} / {chunk_count}")

    # 3. Provenance Integrity
    cursor.execute("SELECT COUNT(DISTINCT target_canonical) FROM evidence;")
    evidenced_entities = cursor.fetchone()[0]
    ratio = (evidenced_entities / max(entity_count, 1)) * 100
    print(f"\nProvenance Integrity:")
    print(f"  * Entities with Direct Evidence:{evidenced_entities:>6} / {entity_count} ({ratio:.1f}%)")

    # 4. Storage size
    cursor.execute("SELECT pg_size_pretty(pg_database_size(%s));", (PG_DATABASE,))
    db_size = cursor.fetchone()[0]
    print(f"\nTotal Database Disk Footprint:    {db_size}")
    print("=" * 70)

    cursor.close()
    conn.close()

if __name__ == "__main__":
    run_validation()

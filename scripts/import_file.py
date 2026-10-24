# -*- coding: utf-8 -*-
"""
Single Document Ingestion Script
Imports a single Markdown document into Archon-KB:
- Full document storage (zero data loss)
- Structural chunking (heading hierarchy, code blocks, tables)
- Entity, Property, Method & Relationship extraction
- Provenance & Evidence tracking with verbatim citations
- Embedding and tsvector generation for hybrid search
"""

import os
import sys
import argparse
import psycopg2
from psycopg2.extras import Json

# Ensure project root is on path
kb_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if kb_root not in sys.path:
    sys.path.insert(0, kb_root)

from src.config import PG_HOST, PG_PORT, PG_DATABASE, PG_USER, PG_PASSWORD
from src.parser.markdown_parser import MarkdownParser
from src.extraction.entity_extractor import EntityExtractor
from src.embeddings.embedding_engine import EmbeddingEngine
from src.normalization.normalizer import EntityNormalizer

def get_connection():
    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DATABASE,
        user=PG_USER,
        password=PG_PASSWORD
    )

def import_file(file_path: str):
    abs_path = os.path.abspath(file_path)
    if not os.path.exists(abs_path):
        print(f"[-] Error: File not found: {abs_path}")
        return False

    print("=" * 70)
    print(f"[*] Ingesting: {abs_path}")
    print("=" * 70)

    # 1. Parse document
    doc = MarkdownParser.parse_file(abs_path)
    print(f"  * Title:      {doc.title}")
    print(f"  * Category:   {doc.category}")
    print(f"  * Size:       {doc.byte_size:,} bytes | {doc.line_count:,} lines")
    print(f"  * Chunks:     {len(doc.chunks):,} structural chunks")
    print(f"  * SHA256:     {doc.content_hash[:16]}...")

    conn = get_connection()
    conn.autocommit = False
    cursor = conn.cursor()
    embedder = EmbeddingEngine()

    try:
        # 2. Upsert document
        cursor.execute("""
            INSERT INTO documents (path, filename, title, category, content, content_hash, line_count, byte_size, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (path) DO UPDATE SET
                title = EXCLUDED.title,
                category = EXCLUDED.category,
                content = EXCLUDED.content,
                content_hash = EXCLUDED.content_hash,
                line_count = EXCLUDED.line_count,
                byte_size = EXCLUDED.byte_size,
                metadata = EXCLUDED.metadata,
                updated_at = NOW()
            RETURNING id;
        """, (
            doc.path,
            doc.filename,
            doc.title,
            doc.category,
            doc.content,
            doc.content_hash,
            doc.line_count,
            doc.byte_size,
            Json({})
        ))
        doc_id = cursor.fetchone()[0]

        # 3. Clean old chunks and evidence for this doc
        cursor.execute("DELETE FROM evidence WHERE document_id = %s;", (doc_id,))
        cursor.execute("DELETE FROM chunks WHERE document_id = %s;", (doc_id,))

        # 4. Insert chunks and generate embeddings
        chunk_texts = [c.content for c in doc.chunks]
        chunk_vectors = embedder.embed_batch(chunk_texts)

        chunk_id_map = {}
        for idx, chunk in enumerate(doc.chunks):
            cursor.execute("""
                INSERT INTO chunks (document_id, chunk_index, heading_path, chunk_type, content, content_hash, start_line, end_line, embedding, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
            """, (
                doc_id,
                chunk.chunk_index,
                chunk.heading_path,
                chunk.chunk_type,
                chunk.content,
                chunk.content_hash,
                chunk.start_line,
                chunk.end_line,
                chunk_vectors[idx],
                Json(chunk.metadata)
            ))
            chunk_id_map[chunk.chunk_index] = cursor.fetchone()[0]

        # 5. Extract entities, properties, methods, relationships, and evidence
        total_ents = 0
        total_rels = 0

        for chunk in doc.chunks:
            ents, props, meths, rels, evs = EntityExtractor.extract_from_chunk(doc, chunk)
            c_id = chunk_id_map.get(chunk.chunk_index)

            # Upsert Entities
            for ent in ents:
                cursor.execute("""
                    INSERT INTO entities (canonical_name, entity_type, name, subsystem, description, aliases, metadata, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (canonical_name) DO UPDATE SET
                        aliases = array_cat(entities.aliases, EXCLUDED.aliases),
                        subsystem = COALESCE(entities.subsystem, EXCLUDED.subsystem),
                        description = COALESCE(entities.description, EXCLUDED.description)
                    RETURNING id;
                """, (
                    ent.canonical_name,
                    ent.entity_type,
                    ent.name,
                    ent.subsystem,
                    ent.description,
                    ent.aliases,
                    Json(ent.metadata),
                    embedder.embed_text(f"{ent.name} {ent.description or ''}")
                ))
                ent_db_id = cursor.fetchone()[0]
                total_ents += 1

                # Upsert Properties
                for p in props:
                    if p.entity_canonical == ent.canonical_name:
                        cursor.execute("""
                            INSERT INTO entity_properties (entity_id, name, value, value_type, description, metadata)
                            VALUES (%s, %s, %s, %s, %s, %s);
                        """, (ent_db_id, p.name, p.value, p.value_type, p.description, Json(p.metadata)))

                # Upsert Methods
                for m in meths:
                    if m.entity_canonical == ent.canonical_name:
                        cursor.execute("""
                            INSERT INTO methods (entity_id, name, language, implementation, description, metadata)
                            VALUES (%s, %s, %s, %s, %s, %s);
                        """, (ent_db_id, m.name, m.language, m.implementation, m.description, Json(m.metadata)))

            # Insert Evidence
            for ev in evs:
                cursor.execute("""
                    INSERT INTO evidence (document_id, chunk_id, target_canonical, source_file, heading_path, location_line, source_text, confidence, extraction_rule)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
                """, (
                    doc_id,
                    c_id,
                    ev.target_canonical,
                    ev.source_file,
                    ev.heading_path,
                    ev.start_line,
                    ev.source_text,
                    ev.confidence,
                    ev.extraction_rule
                ))

            # Upsert Relationships
            for rel in rels:
                cursor.execute("SELECT id FROM entities WHERE canonical_name = %s;", (rel.source_canonical,))
                src_row = cursor.fetchone()
                cursor.execute("SELECT id FROM entities WHERE canonical_name = %s;", (rel.target_canonical,))
                tgt_row = cursor.fetchone()

                if src_row and tgt_row:
                    cursor.execute("""
                        INSERT INTO relationships (source_entity_id, relationship_type, target_entity_id, confidence)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (source_entity_id, relationship_type, target_entity_id) DO NOTHING;
                    """, (src_row[0], rel.relationship_type, tgt_row[0], rel.confidence))
                    total_rels += 1

        conn.commit()
        print(f"[+] Successfully ingested: {len(doc.chunks)} chunks, ~{total_ents} entity mentions, {total_rels} relationships.")
        return True

    except Exception as e:
        conn.rollback()
        print(f"[-] Error during ingestion: {e}")
        raise
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest single Markdown file into Archon-KB")
    parser.add_argument("file", help="Path to markdown file")
    args = parser.parse_args()
    import_file(args.file)

# -*- coding: utf-8 -*-
"""
Upgraded Hybrid Search Engine
Combines:
1. Exact Identifier & Alias Match (Highest priority)
2. Full-Text Search on Entities & Chunks (GIN tsvector + ts_rank)
3. Vector Cosine Similarity on Entities & Chunks (pgvector <=> HNSW)
4. Reciprocal Rank Fusion (RRF) Reranking
5. Entity Knowledge Graph Expansion (Properties, Methods, Relations)
6. Deep Markdown Chunk Context (Code blocks, Tables, Explanations)
7. Exact Provenance (Source file, Heading path, Line numbers, Verbatim citations)
"""

import re
from typing import List, Dict, Any, Optional

class HybridSearchEngine:
    STOP_WORDS = {
        'and', 'or', 'the', 'in', 'of', 'a', 'an', 'to', 'for', 'on', 'with', 'by',
        'as', 'at', 'from', 'is', 'it', 'this', 'that', 'these', 'those', 'be', 'are'
    }

    def __init__(self, db_conn, embedding_engine):
        self.conn = db_conn
        self.embedder = embedding_engine

    def _build_or_tsquery(self, query: str) -> str:
        tokens = [re.sub(r'[^a-zA-Z0-9_]', '', t).lower() for t in query.split()]
        tokens = [t for t in tokens if t and t not in self.STOP_WORDS]
        if tokens:
            return ' | '.join(tokens)
        return query.strip()

    def search(self, query: str, filters: Optional[Dict[str, Any]] = None, limit: int = 5) -> Dict[str, Any]:
        query_clean = query.strip()
        if not query_clean:
            return {'entities': [], 'chunks': []}

        or_query = self._build_or_tsquery(query_clean)
        query_vec = self.embedder.embed_text(query_clean)
        cursor = self.conn.cursor()

        results_by_entity = {}

        # -------------------------------------------------------------
        # 1. ENTITY SEARCH: EXACT IDENTIFIER MATCH (Boost: +2.5)
        # -------------------------------------------------------------
        cursor.execute("""
            SELECT id, canonical_name, name, entity_type, subsystem, description, aliases, metadata,
                   2.5 AS score, 'EXACT_IDENTIFIER_MATCH' AS why_matched
            FROM entities
            WHERE LOWER(name) = LOWER(%s)
               OR LOWER(canonical_name) = LOWER(%s)
               OR LOWER(%s) = ANY(SELECT LOWER(unnest(aliases)))
        """, (query_clean, query_clean, query_clean))

        for row in cursor.fetchall():
            ent_id = str(row[0])
            results_by_entity[ent_id] = {
                'id': ent_id,
                'canonical_name': row[1],
                'name': row[2],
                'entity_type': row[3],
                'subsystem': row[4],
                'description': row[5],
                'aliases': row[6],
                'metadata': row[7],
                'score': float(row[8]),
                'why_matched': row[9]
            }

        # -------------------------------------------------------------
        # 2. ENTITY SEARCH: FULL-TEXT LEXICAL SEARCH
        # -------------------------------------------------------------
        cursor.execute("""
            SELECT id, canonical_name, name, entity_type, subsystem, description, aliases, metadata,
                   (CASE WHEN tsv @@ plainto_tsquery('english', %(q)s) THEN 2.0 * ts_rank_cd(tsv, plainto_tsquery('english', %(q)s)) ELSE 0.0 END
                    + CASE WHEN tsv @@ to_tsquery('english', %(or_q)s) THEN 0.8 * ts_rank_cd(tsv, to_tsquery('english', %(or_q)s)) ELSE 0.0 END) AS rank_score,
                   'FULL_TEXT_LEXICAL' AS why_matched
            FROM entities
            WHERE tsv @@ plainto_tsquery('english', %(q)s) OR tsv @@ to_tsquery('english', %(or_q)s)
            ORDER BY rank_score DESC
            LIMIT %(lim)s;
        """, {'q': query_clean, 'or_q': or_query, 'lim': limit * 2})

        for rank, row in enumerate(cursor.fetchall(), start=1):
            ent_id = str(row[0])
            rrf_score = float(1.0 / (60 + rank))
            if ent_id in results_by_entity:
                results_by_entity[ent_id]['score'] = float(results_by_entity[ent_id]['score']) + rrf_score
            else:
                results_by_entity[ent_id] = {
                    'id': ent_id,
                    'canonical_name': row[1],
                    'name': row[2],
                    'entity_type': row[3],
                    'subsystem': row[4],
                    'description': row[5],
                    'aliases': row[6],
                    'metadata': row[7],
                    'score': rrf_score,
                    'why_matched': row[9]
                }

        # -------------------------------------------------------------
        # 3. ENTITY SEARCH: VECTOR COSINE SIMILARITY (pgvector <=> HNSW)
        # -------------------------------------------------------------
        cursor.execute("""
            SELECT id, canonical_name, name, entity_type, subsystem, description, aliases, metadata,
                   1 - (embedding <=> %s::vector) AS sim,
                   'VECTOR_SEMANTIC' AS why_matched
            FROM entities
            ORDER BY embedding <=> %s::vector ASC
            LIMIT %s;
        """, (query_vec, query_vec, limit * 2))

        for rank, row in enumerate(cursor.fetchall(), start=1):
            ent_id = str(row[0])
            rrf_score = float(1.0 / (60 + rank))
            if ent_id in results_by_entity:
                results_by_entity[ent_id]['score'] = float(results_by_entity[ent_id]['score']) + rrf_score
            else:
                results_by_entity[ent_id] = {
                    'id': ent_id,
                    'canonical_name': row[1],
                    'name': row[2],
                    'entity_type': row[3],
                    'subsystem': row[4],
                    'description': row[5],
                    'aliases': row[6],
                    'metadata': row[7],
                    'score': rrf_score,
                    'why_matched': row[9]
                }

        sorted_entities = sorted(results_by_entity.values(), key=lambda x: x['score'], reverse=True)[:limit]

        # Expand properties, methods, relationships, and evidence for entities
        final_entities = []
        for ent in sorted_entities:
            ent_id = ent['id']

            # Properties
            cursor.execute("SELECT name, value, description FROM entity_properties WHERE entity_id = %s;", (ent_id,))
            ent['properties'] = [{'name': r[0], 'value': r[1], 'description': r[2]} for r in cursor.fetchall()]

            # Methods
            cursor.execute("SELECT name, language, implementation, description FROM methods WHERE entity_id = %s;", (ent_id,))
            ent['methods'] = [{'name': r[0], 'language': r[1], 'implementation': r[2], 'description': r[3]} for r in cursor.fetchall()]

            # Relationships
            cursor.execute("""
                SELECT r.relationship_type, e.name, e.canonical_name, e.entity_type
                FROM relationships r
                JOIN entities e ON r.target_entity_id = e.id
                WHERE r.source_entity_id = %s;
            """, (ent_id,))
            ent['outgoing_relations'] = [{'type': r[0], 'target': r[1], 'canonical': r[2], 'target_type': r[3]} for r in cursor.fetchall()]

            cursor.execute("""
                SELECT r.relationship_type, e.name, e.canonical_name, e.entity_type
                FROM relationships r
                JOIN entities e ON r.source_entity_id = e.id
                WHERE r.target_entity_id = %s;
            """, (ent_id,))
            ent['incoming_relations'] = [{'type': r[0], 'source': r[1], 'canonical': r[2], 'source_type': r[3]} for r in cursor.fetchall()]

            final_entities.append(ent)

        # -------------------------------------------------------------
        # 4. CHUNK SEARCH: DEEP TECHNICAL MARKDOWN CONTEXT (RAG CHUNKS)
        # -------------------------------------------------------------
        cand_limit = max(limit * 5, 20)
        cursor.execute("""
            WITH fts AS (
                SELECT id, document_id, heading_path, chunk_type, content, start_line, end_line,
                       (CASE WHEN tsv @@ plainto_tsquery('english', %(q)s) THEN 2.0 * ts_rank_cd(tsv, plainto_tsquery('english', %(q)s)) ELSE 0.0 END
                        + CASE WHEN tsv @@ to_tsquery('english', %(or_q)s) THEN 0.8 * ts_rank_cd(tsv, to_tsquery('english', %(or_q)s)) ELSE 0.0 END) AS fts_score,
                       ROW_NUMBER() OVER (
                           ORDER BY (CASE WHEN tsv @@ plainto_tsquery('english', %(q)s) THEN 2.0 * ts_rank_cd(tsv, plainto_tsquery('english', %(q)s)) ELSE 0.0 END
                                     + CASE WHEN tsv @@ to_tsquery('english', %(or_q)s) THEN 0.8 * ts_rank_cd(tsv, to_tsquery('english', %(or_q)s)) ELSE 0.0 END) DESC
                       ) AS fts_rank
                FROM chunks
                WHERE tsv @@ plainto_tsquery('english', %(q)s) OR tsv @@ to_tsquery('english', %(or_q)s)
                ORDER BY fts_score DESC
                LIMIT %(cand_limit)s
            ),
            vec AS (
                SELECT id, document_id, heading_path, chunk_type, content, start_line, end_line,
                       1 - (embedding <=> %(vec)s::vector) AS vec_score,
                       ROW_NUMBER() OVER (ORDER BY embedding <=> %(vec)s::vector ASC) AS vec_rank
                FROM chunks
                ORDER BY embedding <=> %(vec)s::vector ASC
                LIMIT %(cand_limit)s
            )
            SELECT COALESCE(f.id, v.id),
                   COALESCE(f.heading_path, v.heading_path),
                   COALESCE(f.chunk_type, v.chunk_type),
                   COALESCE(f.content, v.content),
                   COALESCE(f.start_line, v.start_line),
                   COALESCE(f.end_line, v.end_line),
                   (COALESCE(1.0 / (60 + f.fts_rank), 0.0) + COALESCE(1.0 / (60 + v.vec_rank), 0.0)) AS combined_score
            FROM fts f
            FULL OUTER JOIN vec v ON f.id = v.id
            ORDER BY combined_score DESC
            LIMIT %(limit)s;
        """, {'q': query_clean, 'or_q': or_query, 'vec': query_vec, 'cand_limit': cand_limit, 'limit': limit})

        chunks_found = []
        for r in cursor.fetchall():
            chunks_found.append({
                'chunk_id': str(r[0]),
                'heading_path': r[1],
                'chunk_type': r[2],
                'content': r[3],
                'start_line': r[4],
                'end_line': r[5],
                'score': float(r[6])
            })

        return {
            'query': query_clean,
            'entities': final_entities,
            'chunks': chunks_found
        }

# -*- coding: utf-8 -*-
"""
LLM Agent Retrieval Interface (High Information Density)
Designed specifically for AI agents, pairing maximum technical precision
with minimal token overhead and zero hallucination risk.
"""

import os
import sys
import psycopg2

try:
    from ..config import PG_HOST, PG_PORT, PG_DATABASE, PG_USER, PG_PASSWORD
except Exception:
    PG_HOST = os.environ.get("PGHOST", "localhost")
    PG_PORT = int(os.environ.get("PGPORT", "5432"))
    PG_DATABASE = os.environ.get("PGDATABASE", "technical_kb")
    PG_USER = os.environ.get("PGUSER", "postgres")
    PG_PASSWORD = os.environ.get("PGPASSWORD", "postgres")

from ..embeddings.embedding_engine import EmbeddingEngine
from ..retrieval.hybrid_search import HybridSearchEngine

class LLMKnowledgeBase:
    """
    Core toolset for LLM agents to query the Technical Knowledge Base.
    """
    def __init__(self, db_conn=None):
        if db_conn is None:
            self.conn = psycopg2.connect(
                host=PG_HOST,
                port=PG_PORT,
                dbname=PG_DATABASE,
                user=PG_USER,
                password=PG_PASSWORD
            )
        else:
            self.conn = db_conn
        self.embedder = EmbeddingEngine()
        self.engine = HybridSearchEngine(self.conn, self.embedder)

    def lookup(self, identifier: str) -> dict:
        """
        Fast direct lookup by technical identifier:
        - IOCTL (0x800021DC, etc.)
        - Function name / RVA (DeviceIoControl, 0x1800C1430)
        - WMI Class (Win32_BIOS, WmiMonitorID)
        - Driver / Device name
        Returns a complete, token-dense technical entity card in 1 call.
        """
        clean = identifier.strip()
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT id, canonical_name, name, entity_type, subsystem, description, aliases
            FROM entities
            WHERE LOWER(name) = LOWER(%s)
               OR LOWER(canonical_name) = LOWER(%s)
               OR LOWER(%s) = ANY(SELECT LOWER(unnest(aliases)))
            LIMIT 1;
        """, (clean, clean, clean))

        row = cursor.fetchone()
        if not row:
            # Fallback to hybrid search
            search_res = self.engine.search(clean, limit=1)
            if search_res.get('entities'):
                return self._format_entity(search_res['entities'][0])
            return {"status": "NOT_FOUND", "query": clean}

        ent_id, canonical, name, etype, subsys, desc, aliases = row
        ent_obj = {
            'id': str(ent_id),
            'canonical_name': canonical,
            'name': name,
            'entity_type': etype,
            'subsystem': subsys,
            'description': desc,
            'aliases': aliases
        }

        # Fetch properties
        cursor.execute("SELECT name, value, description FROM entity_properties WHERE entity_id = %s;", (ent_id,))
        ent_obj['properties'] = [{'name': r[0], 'value': r[1], 'description': r[2]} for r in cursor.fetchall()]

        # Fetch methods / implementation
        cursor.execute("SELECT name, language, implementation, description FROM methods WHERE entity_id = %s;", (ent_id,))
        ent_obj['methods'] = [{'name': r[0], 'language': r[1], 'implementation': r[2], 'description': r[3]} for r in cursor.fetchall()]

        # Fetch graph relationships
        cursor.execute("""
            SELECT r.relationship_type, e.name, e.canonical_name, e.entity_type
            FROM relationships r JOIN entities e ON r.target_entity_id = e.id
            WHERE r.source_entity_id = %s;
        """, (ent_id,))
        ent_obj['outgoing_relations'] = [{'type': r[0], 'target': r[1], 'canonical': r[2], 'target_type': r[3]} for r in cursor.fetchall()]

        cursor.execute("""
            SELECT r.relationship_type, e.name, e.canonical_name, e.entity_type
            FROM relationships r JOIN entities e ON r.source_entity_id = e.id
            WHERE r.target_entity_id = %s;
        """, (ent_id,))
        ent_obj['incoming_relations'] = [{'type': r[0], 'source': r[1], 'canonical': r[2], 'source_type': r[3]} for r in cursor.fetchall()]

        # Fetch closest evidence
        cursor.execute("""
            SELECT source_file, heading_path, location_line, source_text
            FROM evidence WHERE target_canonical = %s LIMIT 1;
        """, (canonical,))
        ev_row = cursor.fetchone()
        if ev_row:
            ent_obj['evidence'] = {
                'file': ev_row[0],
                'heading': ev_row[1],
                'line': ev_row[2],
                'source_text': ev_row[3]
            }

        return self._format_entity(ent_obj)

    def search(self, query: str, limit: int = 3) -> dict:
        """
        Hybrid search combining semantic + lexical retrieval.
        Returns matching entities + verbatim markdown code chunks.
        """
        res = self.engine.search(query, limit=limit)
        formatted_entities = [self._format_entity(e) for e in res.get('entities', [])]
        formatted_chunks = []
        for c in res.get('chunks', []):
            formatted_chunks.append({
                'chunk_type': c['chunk_type'],
                'lines': f"{c['start_line']}-{c['end_line']}",
                'section': " -> ".join(c['heading_path'] or []),
                'content': c['content']
            })

        return {
            "query": query,
            "entities": formatted_entities,
            "relevant_chunks": formatted_chunks
        }

    def _format_entity(self, e: dict) -> dict:
        """
        Compacts entity into a clean, token-dense structure.
        """
        out = {
            "name": e['name'],
            "canonical": e.get('canonical_name'),
            "type": e.get('entity_type'),
            "subsystem": e.get('subsystem'),
            "description": e.get('description'),
        }

        if e.get('properties'):
            out['properties'] = {p['name']: (p.get('value') or p.get('description')) for p in e['properties']}

        if e.get('methods'):
            out['implementations'] = [{
                "name": m['name'],
                "lang": m.get('language'),
                "code": m.get('implementation')
            } for m in e['methods']]

        relations = {}
        for r in e.get('outgoing_relations', []):
            relations.setdefault(r['type'], []).append(f"{r['target']} ({r['target_type']})")
        for r in e.get('incoming_relations', []):
            relations.setdefault(f"INCOMING_{r['type']}", []).append(f"{r['source']} ({r['source_type']})")
        if relations:
            out['graph_relations'] = relations

        if e.get('evidence'):
            out['provenance'] = e['evidence']

        return out

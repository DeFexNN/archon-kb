# -*- coding: utf-8 -*-
"""
Knowledge Base Service & LLM Tools API
Provides high-level retrieval functions for LLM agents:
- search(query)
- get_entity(entity_id)
- get_entity_children(entity_id)
- get_properties(entity_id)
- get_methods(entity_id)
- get_relationships(entity_id)
- get_evidence(entity_id)
- find_by_identifier(identifier)
"""

from typing import Dict, Any, List, Optional
from ..retrieval.hybrid_search import HybridSearchEngine

class KnowledgeBaseService:
    def __init__(self, db_conn, embedding_engine):
        self.conn = db_conn
        self.search_engine = HybridSearchEngine(db_conn, embedding_engine)

    def search(self, query: str, filters: Optional[Dict[str, Any]] = None, limit: int = 10) -> Dict[str, Any]:
        """
        Unified search API combining exact match, full text, vector similarity, reranking, and expansion.
        """
        return self.search_engine.search(query, filters=filters, limit=limit)

    def find_by_identifier(self, identifier: str) -> Optional[Dict[str, Any]]:
        """
        Direct exact match for technical identifiers (WMI classes, APIs, IOCTLs, registry keys).
        """
        cursor = self.conn.cursor()
        clean = identifier.strip()
        cursor.execute("""
            SELECT id, canonical_name, name, entity_type, subsystem, description, aliases, metadata
            FROM entities
            WHERE LOWER(name) = LOWER(%s)
               OR LOWER(canonical_name) = LOWER(%s)
               OR LOWER(%s) = ANY(SELECT LOWER(unnest(aliases)))
            LIMIT 1
        """, (clean, clean, clean))
        row = cursor.fetchone()
        if not row:
            return None
        ent_id = str(row[0])
        return self.get_entity(ent_id)

    def get_entity(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetches an entity with all properties, methods, relationships, and evidence.
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, canonical_name, name, entity_type, subsystem, description, aliases, metadata
            FROM entities
            WHERE id = %s OR canonical_name = %s
        """, (entity_id, entity_id))
        row = cursor.fetchone()
        if not row:
            return None

        actual_id = str(row[0])
        canonical = row[1]
        
        ent = {
            'id': actual_id,
            'canonical_name': canonical,
            'name': row[2],
            'entity_type': row[3],
            'subsystem': row[4],
            'description': row[5],
            'aliases': row[6],
            'metadata': row[7],
            'properties': self.get_properties(actual_id),
            'methods': self.get_methods(actual_id),
            'relationships': self.get_relationships(actual_id),
            'evidence': self.get_evidence(canonical)
        }
        return ent

    def get_properties(self, entity_id: str) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT name, value, value_type, description, metadata
            FROM entity_properties
            WHERE entity_id = %s
        """, (entity_id,))
        return [{
            'name': r[0],
            'value': r[1],
            'value_type': r[2],
            'description': r[3],
            'metadata': r[4]
        } for r in cursor.fetchall()]

    def get_methods(self, entity_id: str) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT name, language, implementation, description, metadata
            FROM methods
            WHERE entity_id = %s
        """, (entity_id,))
        return [{
            'name': r[0],
            'language': r[1],
            'implementation': r[2],
            'description': r[3],
            'metadata': r[4]
        } for r in cursor.fetchall()]

    def get_relationships(self, entity_id: str) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT r.relationship_type, e.id, e.name, e.canonical_name, e.entity_type
            FROM relationships r
            JOIN entities e ON r.target_entity_id = e.id
            WHERE r.source_entity_id = %s
        """, (entity_id,))
        outgoing = [{
            'direction': 'OUTGOING',
            'type': r[0],
            'target_id': str(r[1]),
            'target_name': r[2],
            'target_canonical': r[3],
            'target_type': r[4]
        } for r in cursor.fetchall()]

        cursor.execute("""
            SELECT r.relationship_type, e.id, e.name, e.canonical_name, e.entity_type
            FROM relationships r
            JOIN entities e ON r.source_entity_id = e.id
            WHERE r.target_entity_id = %s
        """, (entity_id,))
        incoming = [{
            'direction': 'INCOMING',
            'type': r[0],
            'source_id': str(r[1]),
            'source_name': r[2],
            'source_canonical': r[3],
            'source_type': r[4]
        } for r in cursor.fetchall()]

        return outgoing + incoming

    def get_entity_children(self, entity_id: str) -> List[Dict[str, Any]]:
        """
        Gets hierarchical child entities linked via CONTAINS or HAS_PROPERTY relationships.
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT e.id, e.name, e.canonical_name, e.entity_type, r.relationship_type
            FROM relationships r
            JOIN entities e ON r.target_entity_id = e.id
            WHERE r.source_entity_id = %s AND r.relationship_type IN ('CONTAINS', 'HAS_PROPERTY')
        """, (entity_id,))
        return [{
            'id': str(r[0]),
            'name': r[1],
            'canonical_name': r[2],
            'entity_type': r[3],
            'relationship_type': r[4]
        } for r in cursor.fetchall()]

    def get_evidence(self, target_canonical: str) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT source_file, heading_path, location_line, source_text, confidence
            FROM evidence
            WHERE target_canonical = %s
        """, (target_canonical,))
        return [{
            'source_file': r[0],
            'heading_path': r[1],
            'location_line': r[2],
            'source_text': r[3],
            'confidence': float(r[4])
        } for r in cursor.fetchall()]

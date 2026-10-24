# -*- coding: utf-8 -*-
"""
Entity Normalizer & Conflict Tracker
Handles canonical naming, alias expansion, and tracks conflicting claims across documents.
"""

from typing import Dict, Any, List

class EntityNormalizer:
    TYPE_MAP = {
        'ioctl': 'ioctl',
        'api': 'api_function',
        'api_function': 'api_function',
        'wmi_class': 'wmi_class',
        'class': 'wmi_class',
        'wmi_namespace': 'wmi_namespace',
        'namespace': 'wmi_namespace',
        'structure': 'structure',
        'struct': 'structure',
        'property': 'property',
        'driver': 'driver',
        'device': 'device',
        'hardware_component': 'hardware_component',
        'registry_key': 'registry_key',
        'checksum_algorithm': 'checksum_algorithm',
        'crypto_algorithm': 'crypto_algorithm',
        'smbios_type': 'smbios_type'
    }

    @classmethod
    def normalize_entity_type(cls, raw_type: str) -> str:
        clean = raw_type.strip().lower()
        return cls.TYPE_MAP.get(clean, clean)

    @staticmethod
    def canonicalize_name(raw_name: str, entity_type: str) -> str:
        clean = raw_name.strip()
        clean = clean.replace('\\', '.').replace('/', '.')
        clean = clean.replace('{', '').replace('}', '').replace('"', '').replace("'", "")
        return f"{entity_type}.{clean.lower()}"

    @staticmethod
    def merge_entities(existing: Dict[str, Any], new_entity: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merges new entity information into existing canonical entity without losing knowledge.
        Tracks aliases, conflicts, and increments appearance frequency.
        """
        # Merge aliases
        existing_aliases = set(existing.get('aliases', []))
        for a in new_entity.get('aliases', []):
            existing_aliases.add(a)
        existing['aliases'] = list(existing_aliases)

        # Merge descriptions or track variation
        if new_entity.get('description') and new_entity['description'] != existing.get('description'):
            variations = existing.setdefault('metadata', {}).setdefault('description_variations', [])
            if new_entity['description'] not in variations:
                variations.append(new_entity['description'])

        existing.setdefault('metadata', {})['frequency'] = existing.get('metadata', {}).get('frequency', 1) + 1
        return existing

    @staticmethod
    def record_conflict(existing: Dict[str, Any], property_name: str, old_val: Any, new_val: Any, source_file: str):
        """
        Records conflicting claims without silently overwriting.
        """
        conflicts = existing.setdefault('metadata', {}).setdefault('conflicts', [])
        conflicts.append({
            'property': property_name,
            'existing_value': old_val,
            'conflicting_value': new_val,
            'source_file': source_file
        })

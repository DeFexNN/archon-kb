# -*- coding: utf-8 -*-
import unittest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.parser.markdown_parser import MarkdownChunk, ParsedDocument
from src.extraction.entity_extractor import EntityExtractor
from src.normalization.normalizer import EntityNormalizer

class TestEntityExtractorFixtures(unittest.TestCase):

    def test_smbios_types_extracted_positive(self):
        text = """
Full SMBIOS blob: Types 0 (BIOS), 1 (System UUID/SKU), 2 (Baseboard), 3 (Chassis), 4 (CPU), 11 (OEM strings), 17 (Memory serials).
Also by spoofing the SerialNumber field in SMBIOS table type 17.
"""
        chunk = MarkdownChunk(
            chunk_index=0,
            heading_path=["Firmware Analysis", "SMBIOS / RSMB / WMI"],
            chunk_type="text",
            content=text,
            start_line=1,
            end_line=5
        )
        doc = ParsedDocument("specs.md", "specs.md", "Specs", text, "Specs", [chunk])
        entities, props, meths, rels, evs = EntityExtractor.extract_from_chunk(doc, chunk)
        
        canonicals = {e.canonical_name for e in entities}
        self.assertIn("smbios.type_0", canonicals)
        self.assertIn("smbios.type_1", canonicals)
        self.assertIn("smbios.type_2", canonicals)
        self.assertIn("smbios.type_11", canonicals)
        self.assertIn("smbios.type_17", canonicals)

    def test_smbios_negative_non_smbios(self):
        text = """
The function returns data of type 2 and type 4 in case of error.
Memory allocation type A is unsupported.
"""
        chunk = MarkdownChunk(
            chunk_index=0,
            heading_path=["Algorithm Details"],
            chunk_type="text",
            content=text,
            start_line=1,
            end_line=3
        )
        doc = ParsedDocument("algo.md", "algo.md", "Algorithm", text, "Algo", [chunk])
        entities, props, meths, rels, evs = EntityExtractor.extract_from_chunk(doc, chunk)
        
        canonicals = {e.canonical_name for e in entities}
        smbios_ents = [c for c in canonicals if c.startswith("smbios.type_")]
        self.assertEqual(len(smbios_ents), 0, f"False positives found: {smbios_ents}")

    def test_ioctl_and_api_extraction(self):
        text = """
The driver dispatches IOCTL_STORAGE_QUERY_PROPERTY and 0x800021DC via DeviceIoControl.
It invokes NtQuerySystemInformation and RtlInitUnicodeString in kernel mode.
"""
        chunk = MarkdownChunk(
            chunk_index=0,
            heading_path=["Driver Dispatch"],
            chunk_type="text",
            content=text,
            start_line=1,
            end_line=4
        )
        doc = ParsedDocument("driver.md", "driver.md", "Driver", text, "Driver", [chunk])
        entities, props, meths, rels, evs = EntityExtractor.extract_from_chunk(doc, chunk)

        canonicals = {e.canonical_name for e in entities}
        self.assertIn("ioctl.0x800021dc", canonicals)
        self.assertIn("api.win32.DeviceIoControl", canonicals)
        self.assertIn("api.ntdll.NtQuerySystemInformation", canonicals)
        self.assertIn("api.ntdll.RtlInitUnicodeString", canonicals)

    def test_entity_type_normalization(self):
        norm_type = EntityNormalizer.normalize_entity_type("IOCTL")
        self.assertEqual(norm_type, "ioctl")
        norm_api = EntityNormalizer.normalize_entity_type("API")
        self.assertEqual(norm_api, "api_function")

if __name__ == "__main__":
    unittest.main()

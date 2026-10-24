# -*- coding: utf-8 -*-
import unittest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.parser.markdown_parser import MarkdownParser

class TestMarkdownParserFixtures(unittest.TestCase):

    def test_code_block_preserved(self):
        content = """# Heading 1
Some introductory text.

```cpp
#pragma pack(push, 1)
typedef struct _SMBIOS_HEADER {
    BYTE Type;
    BYTE Length;
    WORD Handle;
} SMBIOS_HEADER, *PSMBIOS_HEADER;
```

Concluding paragraph.
"""
        doc = MarkdownParser.parse_content("test_code.md", content)
        code_chunks = [c for c in doc.chunks if c.chunk_type == "code"]
        self.assertEqual(len(code_chunks), 1)
        self.assertIn("typedef struct _SMBIOS_HEADER", code_chunks[0].content)
        self.assertEqual(code_chunks[0].metadata.get("language"), "cpp")

    def test_table_preserved(self):
        content = """# Section
| # | Type | Name |
|---|---|---|
| 1 | 0 | BIOS Information |
| 2 | 1 | System Information |
"""
        doc = MarkdownParser.parse_content("test_table.md", content)
        table_chunks = [c for c in doc.chunks if c.chunk_type == "table"]
        self.assertEqual(len(table_chunks), 1)
        self.assertIn("BIOS Information", table_chunks[0].content)
        self.assertTrue(table_chunks[0].metadata.get("is_table"))

    def test_heading_hierarchy_stacked(self):
        content = """# Chapter 1
Text 1.

## Section 1.1
Text 2.

### Subsection 1.1.1
Text 3.
"""
        doc = MarkdownParser.parse_content("test_heading.md", content)
        h3_chunks = [c for c in doc.chunks if "Subsection 1.1.1" in c.heading_path]
        self.assertGreater(len(h3_chunks), 0)
        self.assertEqual(h3_chunks[0].heading_path, ["Chapter 1", "Section 1.1", "Subsection 1.1.1"])

if __name__ == "__main__":
    unittest.main()

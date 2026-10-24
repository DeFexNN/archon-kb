# -*- coding: utf-8 -*-
"""
Structural Markdown Parser
Preserves heading hierarchy (heading_path), code blocks, tables, and lists.
Ensures zero data loss with line-accurate provenance.
"""

import os
import re
import hashlib
from typing import List, Dict, Any, Optional

class MarkdownChunk:
    def __init__(
        self,
        chunk_index: int,
        heading_path: List[str],
        chunk_type: str,
        content: str,
        start_line: int,
        end_line: int,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.chunk_index = chunk_index
        self.heading_path = heading_path
        self.chunk_type = chunk_type
        self.content = content.strip()
        self.start_line = start_line
        self.end_line = end_line
        self.metadata = metadata or {}
        self.content_hash = hashlib.sha256(self.content.encode('utf-8')).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'chunk_index': self.chunk_index,
            'heading_path': self.heading_path,
            'chunk_type': self.chunk_type,
            'content': self.content,
            'content_hash': self.content_hash,
            'start_line': self.start_line,
            'end_line': self.end_line,
            'metadata': self.metadata
        }

class ParsedDocument:
    def __init__(
        self,
        path: str,
        filename: str,
        title: str,
        content: str,
        category: str,
        chunks: List[MarkdownChunk]
    ):
        self.path = os.path.abspath(path)
        self.filename = filename
        self.title = title
        self.content = content
        self.category = category
        self.content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
        self.line_count = len(content.splitlines())
        self.byte_size = len(content.encode('utf-8'))
        self.chunks = chunks

    def to_dict(self) -> Dict[str, Any]:
        return {
            'path': self.path,
            'filename': self.filename,
            'title': self.title,
            'category': self.category,
            'content': self.content,
            'content_hash': self.content_hash,
            'line_count': self.line_count,
            'byte_size': self.byte_size,
            'chunks': [c.to_dict() for c in self.chunks]
        }

class MarkdownParser:
    HEADING_REGEX = re.compile(r'^(#{1,6})\s+(.*)$')
    CODE_FENCE_REGEX = re.compile(r'^```(\w*)\s*$')

    @classmethod
    def parse_file(cls, file_path: str) -> ParsedDocument:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        return cls.parse_content(file_path, content)

    @classmethod
    def parse_content(cls, file_path: str, content: str) -> ParsedDocument:
        filename = os.path.basename(file_path)
        category = cls._detect_category(file_path, content)
        
        lines = content.splitlines()
        chunks: List[MarkdownChunk] = []

        heading_stack: List[str] = [] # stores current heading per level [level-1]
        current_heading_path: List[str] = []
        document_title = filename

        # State tracking
        chunk_idx = 0
        in_code_block = False
        code_fence_lang = ""
        current_block_lines: List[str] = []
        current_block_type = "text"
        block_start_line = 1

        def flush_current_block(end_line: int):
            nonlocal chunk_idx, current_block_lines, current_block_type, block_start_line
            text = "\n".join(current_block_lines).strip()
            if not text:
                current_block_lines = []
                return
            
            # If current block is text and is a tiny connective fragment,
            # merge it with previous text chunk under same heading path if available
            is_connective_junk = current_block_type == "text" and text.lower() in ('and', 'or', '-', '*', '--', '...', '___', '***')
            if is_connective_junk and chunks and chunks[-1].chunk_type == "text" and chunks[-1].heading_path == current_heading_path:
                chunks[-1].content += "\n\n" + text
                chunks[-1].end_line = end_line
                current_block_lines = []
                return

            meta = {}
            if current_block_type == "code":
                meta["language"] = code_fence_lang
            elif current_block_type == "table":
                meta["is_table"] = True

            chunk = MarkdownChunk(
                chunk_index=chunk_idx,
                heading_path=list(current_heading_path),
                chunk_type=current_block_type,
                content=text,
                start_line=block_start_line,
                end_line=end_line,
                metadata=meta
            )
            chunks.append(chunk)
            chunk_idx += 1
            current_block_lines = []

        for line_num, line in enumerate(lines, start=1):
            stripped = line.strip()

            # Handle code block fences
            fence_match = cls.CODE_FENCE_REGEX.match(stripped)
            if fence_match:
                if not in_code_block:
                    # Starting code block: flush previous text
                    flush_current_block(line_num - 1)
                    in_code_block = True
                    code_fence_lang = fence_match.group(1) or "text"
                    current_block_type = "code"
                    block_start_line = line_num
                    current_block_lines.append(line)
                    continue
                else:
                    # Closing code block
                    current_block_lines.append(line)
                    flush_current_block(line_num)
                    in_code_block = False
                    current_block_type = "text"
                    block_start_line = line_num + 1
                    continue

            if in_code_block:
                current_block_lines.append(line)
                continue

            # Check headings
            heading_match = cls.HEADING_REGEX.match(stripped)
            if heading_match:
                flush_current_block(line_num - 1)
                
                level = len(heading_match.group(1))
                h_text = heading_match.group(2).strip()

                if not document_title or document_title == filename:
                    if level == 1:
                        document_title = h_text

                # Adjust heading stack
                while len(heading_stack) >= level:
                    heading_stack.pop()
                heading_stack.append(h_text)
                current_heading_path = list(heading_stack)

                # Store heading line itself as heading chunk
                block_start_line = line_num
                current_block_type = f"h{level}"
                current_block_lines = [line]
                flush_current_block(line_num)
                
                current_block_type = "text"
                block_start_line = line_num + 1
                continue

            # Check tables
            is_table_line = stripped.startswith('|') and stripped.endswith('|')
            if is_table_line:
                if current_block_type != "table":
                    flush_current_block(line_num - 1)
                    current_block_type = "table"
                    block_start_line = line_num
                current_block_lines.append(line)
                continue
            else:
                if current_block_type == "table":
                    flush_current_block(line_num - 1)
                    current_block_type = "text"
                    block_start_line = line_num

            # Normal text / paragraph
            # Only flush on blank line if current text is substantial (>= 120 chars) or ends with sentence terminator
            if not stripped:
                if current_block_lines:
                    accum_text = "\n".join(current_block_lines).strip()
                    if len(accum_text) >= 120 or accum_text.endswith(('.', '!', '?', ':')):
                        flush_current_block(line_num - 1)
                        current_block_type = "text"
                        block_start_line = line_num + 1
                continue

            if not current_block_lines:
                block_start_line = line_num
            current_block_lines.append(line)

        # Flush any remaining lines at end of document
        flush_current_block(len(lines))

        return ParsedDocument(
            path=file_path,
            filename=filename,
            title=document_title,
            content=content,
            category=category,
            chunks=chunks
        )

    @classmethod
    def _detect_category(cls, file_path: str, content: str) -> str:
        fn_lower = os.path.basename(file_path).lower()
        if any(k in fn_lower for k in ['report', 'inventory', 'analysis', 'devirt', 'rva', 'proof', 're']):
            return 'Reverse Engineering & Audit'
        elif any(k in fn_lower for k in ['criteria', 'audit', 'kernel', 'specs', 'driver']):
            return 'Kernel & System Specs'
        elif any(k in fn_lower for k in ['forum', 'hardware', 'research', 'hwid']):
            return 'Hardware & HWID Research'
        elif any(k in fn_lower for k in ['protocol', 'capture', 'network', 'packet']):
            return 'Network Protocols & Packets'
        elif any(k in fn_lower for k in ['guide', 'faq', 'readme', 'todo', 'changelog', 'worklog']):
            return 'Documentation & Worklogs'
        return 'Technical Architecture & Notes'

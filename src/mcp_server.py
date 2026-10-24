# -*- coding: utf-8 -*-
"""
Model Context Protocol (MCP) Server for Archon-KB Technical Knowledge Base
Provides fast, structured tools for AI agents (Claude Desktop, Antigravity, Cursor, Windsurf).
"""

import os
import sys

# Prevent crash under pythonw.exe or headless environments where stdout/stderr/stdin are None
log_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "mcp_service.log"))
if sys.stdin is None:
    sys.stdin = open(os.devnull, "r")
if sys.stdout is None:
    sys.stdout = open(log_path, "a", buffering=1, encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(log_path, "a", buffering=1, encoding="utf-8")

from fastmcp import FastMCP

# Ensure project root is on path
kb_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if kb_root not in sys.path:
    sys.path.insert(0, kb_root)

from src.api.llm_tools import LLMKnowledgeBase
from src.config import get_recognized_folders

# Initialize FastMCP Server
mcp = FastMCP(
    "Archon-Technical-KB",
    instructions=(
        "This server provides verified technical knowledge from the PostgreSQL/pgvector Technical KB. "
        "Designated for reverse engineering, kernel architecture, systems internals, and related analysis. "
        "If operating outside known project directories, set confirm_project=True to confirm domain intent."
    )
)

kb = None

def get_kb():
    global kb
    if kb is None:
        kb = LLMKnowledgeBase()
    return kb

def verify_project_scope(project_path: str = None, confirm_project: bool = False, project_context: str = None):
    """
    Validates project scope or explicit confirmation from the AI agent.
    Returns: (is_allowed: bool, reason: str)
    """
    # 1. Explicit confirmation from AI agent
    if confirm_project:
        return True, "EXPLICIT_CONFIRMED"

    # 2. Context keyword confirmation
    if project_context and project_context.strip():
        ctx_lower = project_context.lower()
        re_keywords = ["spoofer", "hypervisor", "reverse", "re", "kernel", "driver", "ida", "analysis", "system"]
        if any(k in ctx_lower for k in re_keywords):
            return True, f"CONTEXT_CONFIRMED: {project_context.strip()}"

    recognized_folders = get_recognized_folders()

    # 3. If explicit project_path provided, check it directly
    if project_path:
        norm_p = os.path.normpath(project_path).lower()
        if any(kw in norm_p for kw in recognized_folders):
            return True, f"PATH_RECOGNIZED: {norm_p}"
        return False, "CONFIRMATION_REQUIRED"

    # 4. Path inspection across IDE environment variables
    for env_var in ["WORKSPACE_FOLDER", "PROJECT_DIR", "CURSOR_WORKSPACE", "VSCODE_CWD", "PWD"]:
        val = os.environ.get(env_var)
        if val:
            norm_val = os.path.normpath(val).lower()
            if any(kw in norm_val for kw in recognized_folders):
                return True, f"ENV_RECOGNIZED: {env_var}"
            return False, "CONFIRMATION_REQUIRED"

    # 5. Check current working directory
    cwd = os.path.normpath(os.getcwd()).lower()
    if any(kw in cwd for kw in recognized_folders):
        return True, f"CWD_RECOGNIZED: {cwd}"

    return True, "DEFAULT_ALLOW"

@mcp.tool()
def lookup_technical_entity(
    identifier: str,
    confirm_project: bool = False,
    project_context: str = None,
    project_path: str = None
) -> dict:
    """
    Zero-hallucination lookup for a specific technical identifier.
    Returns canonical properties, implementation methods, graph relationships, and source provenance.
    """
    allowed, reason = verify_project_scope(project_path, confirm_project, project_context)
    if not allowed:
        return {
            "status": "CONFIRMATION_REQUIRED",
            "message": "To query knowledge base outside recognized workspaces, set confirm_project=True."
        }

    engine = get_kb()
    return engine.lookup(identifier)

@mcp.tool()
def search_technical_knowledge(
    query: str,
    limit: int = 3,
    confirm_project: bool = False,
    project_context: str = None,
    project_path: str = None
) -> dict:
    """
    5-stage hybrid retrieval across the knowledge base:
    Combines exact identifier matching, lexical full-text (GIN), and pgvector cosine similarity via RRF.
    """
    allowed, reason = verify_project_scope(project_path, confirm_project, project_context)
    if not allowed:
        return {
            "status": "CONFIRMATION_REQUIRED",
            "message": "To query knowledge base outside recognized workspaces, set confirm_project=True."
        }

    engine = get_kb()
    return engine.search(query, limit=limit)

@mcp.tool()
def get_kb_health_status(
    confirm_project: bool = False,
    project_context: str = None,
    project_path: str = None
) -> dict:
    """
    Returns the current health status, document counts, and integrity metrics of the Technical KB.
    """
    allowed, reason = verify_project_scope(project_path, confirm_project, project_context)
    if not allowed:
        return {
            "status": "CONFIRMATION_REQUIRED",
            "message": "To query knowledge base outside recognized workspaces, set confirm_project=True."
        }

    engine = get_kb()
    cursor = engine.conn.cursor()
    cursor.execute("SELECT count(*) FROM documents;")
    docs = cursor.fetchone()[0]
    cursor.execute("SELECT count(*) FROM chunks;")
    chunks = cursor.fetchone()[0]
    cursor.execute("SELECT count(*) FROM entities;")
    ents = cursor.fetchone()[0]
    cursor.execute("SELECT count(*) FROM relationships;")
    rels = cursor.fetchone()[0]

    return {
        "status": "HEALTHY",
        "scope_status": reason,
        "metrics": {
            "documents": docs,
            "chunks": chunks,
            "entities": ents,
            "relationships": rels
        }
    }

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--sse":
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 8765
        print(f"Starting MCP Server on SSE port {port}...")
        mcp.run(transport="sse", port=port)
    else:
        mcp.run(transport="stdio")

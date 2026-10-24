# -*- coding: utf-8 -*-
"""
Central configuration for Archon-KB.
Loads connection and runtime parameters from environment variables with sensible defaults.
"""

import os
from typing import List

# Database Settings
PG_HOST = os.environ.get("PGHOST", os.environ.get("KB_PG_HOST", "localhost"))
PG_PORT = int(os.environ.get("PGPORT", os.environ.get("KB_PG_PORT", "5432")))
PG_DATABASE = os.environ.get("PGDATABASE", os.environ.get("KB_PG_DATABASE", "technical_kb"))
PG_USER = os.environ.get("PGUSER", os.environ.get("KB_PG_USER", "postgres"))
PG_PASSWORD = os.environ.get("PGPASSWORD", os.environ.get("KB_PG_PASSWORD", "postgres"))

# Embedding Settings
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "local-semantic-384")
EMBEDDING_DIM = int(os.environ.get("EMBEDDING_DIM", "384"))

# Recognized Analysis & Reverse Engineering Workspaces (optional scoping)
_DEFAULT_RECOGNIZED_FOLDERS = [
    "hypervisor", "kernel", "driver", "analysis", "re",
    "ida", "ghidra", "x64dbg", "symbols", "devirt", "knowledge_base"
]

def get_recognized_folders() -> List[str]:
    custom = os.environ.get("KB_RECOGNIZED_FOLDERS")
    if custom:
        return [f.strip().lower() for f in custom.split(",") if f.strip()]
    return _DEFAULT_RECOGNIZED_FOLDERS

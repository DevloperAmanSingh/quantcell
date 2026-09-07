"""
Vector database configuration for Research Agent.

Fault-tolerant, lazy initialization:
- Attempts to create embeddings and a LanceDB vector store only when requested.
- If no embedding provider/API key is available, returns None instead of raising.
- Respects environment variable overrides (e.g., EMBEDDER_MODEL_ID).

This prevents import-time failures and allows the ResearchAgent to run in a
"tools-only" mode without knowledge search when embeddings are not configured.
"""

from loguru import logger

import quantcell.utils.model as model_utils_mod
from quantcell.utils.db import resolve_lancedb_uri

KNOWLEDGE_TABLE_NAME = "research_agent_knowledge_base"


def get_vector_db():
    """Create and return the LanceDB vector store, or None if embeddings are unavailable.

    This function is safe to call at runtime; it will not raise during normal
    missing-configuration scenarios. Unexpected errors are logged and result in
    a None return to enable graceful degradation.
    """
    try:
        embeddings = model_utils_mod.get_embeddings_for_agent("research_agent")
    except Exception as e:
        logger.warning(
            "ResearchAgent embeddings unavailable; disabling knowledge search. Error: {}",
            e,
        )
        return None

    try:
        import lancedb
        from langchain_community.vectorstores import LanceDB

        connection = lancedb.connect(resolve_lancedb_uri())
        return LanceDB(
            connection=connection,
            table_name=KNOWLEDGE_TABLE_NAME,
            embedding=embeddings,
        )
    except Exception as e:
        logger.warning(
            "Failed to initialize LanceDB for ResearchAgent; disabling knowledge. Error: {}",
            e,
        )
        return None

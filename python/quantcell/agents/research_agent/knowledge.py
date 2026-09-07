"""Research agent knowledge base on LangChain + LanceDB.

`KnowledgeBase` wraps the LanceDB vector store with markdown/PDF ingestion
(splitting via langchain-text-splitters) and similarity search. All entry
points degrade gracefully: when embeddings are not configured the knowledge
base is disabled and ingestion becomes a no-op, keeping the agent usable in
tools-only mode.
"""

import asyncio
import tempfile
from pathlib import Path
from typing import List, Optional

import aiofiles
import aiohttp
from loguru import logger

from .vdb import get_vector_db

DEFAULT_SEARCH_RESULTS = 10
_CHUNK_SIZE = 2000
_CHUNK_OVERLAP = 200


class KnowledgeBase:
    """Markdown/PDF ingestion + similarity search over a LanceDB vector store."""

    def __init__(self, vector_store) -> None:
        self.vector_store = vector_store

    async def add_markdown_file(
        self, name: str, path: Path, metadata: Optional[dict] = None
    ) -> int:
        from langchain_text_splitters import MarkdownTextSplitter

        async with aiofiles.open(path, "r", encoding="utf-8") as f:
            text = await f.read()

        splitter = MarkdownTextSplitter(
            chunk_size=_CHUNK_SIZE, chunk_overlap=_CHUNK_OVERLAP
        )
        docs = splitter.create_documents(
            [text], metadatas=[{"name": name, **(metadata or {})}]
        )
        if not docs:
            return 0
        # LanceDB add_documents is synchronous; keep the event loop responsive.
        await asyncio.to_thread(self.vector_store.add_documents, docs)
        return len(docs)

    async def add_pdf_url(self, url: str, metadata: Optional[dict] = None) -> int:
        from langchain_community.document_loaders import PyPDFLoader
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                resp.raise_for_status()
                pdf_bytes = await resp.read()

        with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
            tmp.write(pdf_bytes)
            tmp.flush()
            pages = await asyncio.to_thread(PyPDFLoader(tmp.name).load)

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=_CHUNK_SIZE, chunk_overlap=_CHUNK_OVERLAP
        )
        docs = splitter.split_documents(pages)
        for doc in docs:
            doc.metadata.update({"source": url, **(metadata or {})})
        if not docs:
            return 0
        await asyncio.to_thread(self.vector_store.add_documents, docs)
        return len(docs)

    def search(self, query: str, k: int = DEFAULT_SEARCH_RESULTS) -> List:
        return self.vector_store.similarity_search(query, k=k)


_knowledge_cache: Optional[KnowledgeBase] = None


def get_knowledge() -> Optional[KnowledgeBase]:
    """Lazily create and cache the KnowledgeBase instance.

    Returns None when embeddings/vector DB are unavailable, enabling a
    tools-only mode without knowledge search.
    """
    global _knowledge_cache
    if _knowledge_cache is not None:
        return _knowledge_cache

    vdb = get_vector_db()
    if vdb is None:
        logger.warning(
            "ResearchAgent Knowledge disabled: vector DB unavailable (no embeddings)."
        )
        return None

    _knowledge_cache = KnowledgeBase(vdb)
    return _knowledge_cache


async def insert_md_file_to_knowledge(
    name: str, path: Path, metadata: Optional[dict] = None
):
    knowledge = get_knowledge()
    if knowledge is None:
        logger.warning(
            "Skipping markdown insertion: Knowledge disabled (no embeddings configured)."
        )
        return
    await knowledge.add_markdown_file(name=name, path=path, metadata=metadata)


async def insert_pdf_file_to_knowledge(url: str, metadata: Optional[dict] = None):
    knowledge = get_knowledge()
    if knowledge is None:
        logger.warning(
            "Skipping PDF insertion: Knowledge disabled (no embeddings configured)."
        )
        return
    await knowledge.add_pdf_url(url=url, metadata=metadata)

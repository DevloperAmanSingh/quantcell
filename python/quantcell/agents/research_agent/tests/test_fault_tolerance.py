"""Fault-tolerance tests: ResearchAgent degrades gracefully without embeddings."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Sequence

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

import quantcell.agents.research_agent.knowledge as knowledge_mod
import quantcell.agents.research_agent.vdb as vdb


def _raise_unavailable(*_args, **_kwargs):
    raise ValueError("no embedding provider configured")


@pytest.fixture(autouse=True)
def reset_knowledge_cache():
    knowledge_mod._knowledge_cache = None
    yield
    knowledge_mod._knowledge_cache = None


def test_get_vector_db_returns_none_when_embeddings_unavailable(monkeypatch):
    monkeypatch.setattr(
        vdb.model_utils_mod, "get_embeddings_for_agent", _raise_unavailable
    )
    assert vdb.get_vector_db() is None


def test_get_vector_db_returns_none_when_lancedb_init_fails(monkeypatch):
    monkeypatch.setattr(
        vdb.model_utils_mod, "get_embeddings_for_agent", lambda name: object()
    )

    def _bad_uri():
        raise RuntimeError("disk unavailable")

    monkeypatch.setattr(vdb, "resolve_lancedb_uri", _bad_uri)
    assert vdb.get_vector_db() is None


def test_get_knowledge_returns_none_without_embeddings(monkeypatch):
    monkeypatch.setattr(
        vdb.model_utils_mod, "get_embeddings_for_agent", _raise_unavailable
    )
    assert knowledge_mod.get_knowledge() is None


@pytest.mark.asyncio
async def test_insert_functions_noop_when_disabled(monkeypatch, tmp_path):
    monkeypatch.setattr(
        vdb.model_utils_mod, "get_embeddings_for_agent", _raise_unavailable
    )
    md = tmp_path / "doc.md"
    md.write_text("# hello")
    # Must not raise despite knowledge being disabled
    await knowledge_mod.insert_md_file_to_knowledge("doc", md)
    await knowledge_mod.insert_pdf_file_to_knowledge("http://example.com/x.pdf")


class _FakeVectorStore:
    def __init__(self):
        self.added = []

    def add_documents(self, docs):
        self.added.extend(docs)

    def similarity_search(self, query, k=10):
        return [SimpleNamespace(page_content=f"result for {query} (k={k})")]


@pytest.mark.asyncio
async def test_knowledge_base_markdown_ingestion_and_search(tmp_path):
    store = _FakeVectorStore()
    kb = knowledge_mod.KnowledgeBase(store)

    md = tmp_path / "filing.md"
    md.write_text("# Apple 10-K\n\nRevenue grew 5% year over year.")
    count = await kb.add_markdown_file("apple-10k", md, metadata={"ticker": "AAPL"})

    assert count == len(store.added) > 0
    assert store.added[0].metadata["name"] == "apple-10k"
    assert store.added[0].metadata["ticker"] == "AAPL"

    results = kb.search("apple revenue")
    assert "apple revenue" in results[0].page_content


class _FakeReactModel(GenericFakeChatModel):
    def bind_tools(self, tools: Sequence[Any], **kwargs: Any):
        return self


def test_research_agent_initializes_without_knowledge_when_embeddings_missing(
    monkeypatch,
):
    import quantcell.agents.research_agent.core as core_mod

    monkeypatch.setattr(core_mod, "get_knowledge", lambda: None)
    monkeypatch.setattr(
        core_mod.model_utils_mod,
        "get_chat_model_for_agent",
        lambda name, **kw: _FakeReactModel(messages=iter([AIMessage(content="ok")])),
    )

    agent = core_mod.ResearchAgent()
    assert agent.knowledge is None
    tool_names = [getattr(t, "__name__", str(t)) for t in agent.tools]
    assert "search_knowledge_base" not in tool_names
    assert "web_search" in tool_names


def test_research_agent_adds_knowledge_tool_when_available(monkeypatch):
    import quantcell.agents.research_agent.core as core_mod

    kb = knowledge_mod.KnowledgeBase(_FakeVectorStore())
    monkeypatch.setattr(core_mod, "get_knowledge", lambda: kb)
    monkeypatch.setattr(
        core_mod.model_utils_mod,
        "get_chat_model_for_agent",
        lambda name, **kw: _FakeReactModel(messages=iter([AIMessage(content="ok")])),
    )

    agent = core_mod.ResearchAgent()
    assert agent.knowledge is kb
    tool_names = [getattr(t, "__name__", str(t)) for t in agent.tools]
    assert "search_knowledge_base" in tool_names

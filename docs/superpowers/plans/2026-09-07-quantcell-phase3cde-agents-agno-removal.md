# QuantCell Phase 3c–3e: Agent Migration + Agno Removal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate ResearchAgent, NewsAgent, and the trading LLM composers to LangGraph/LangChain, then delete Agno from the codebase and dependencies.

**Architecture:**
- **Embeddings factory** added to `langchain_factory.py` (OpenAI-family/Google/Azure/Ollama embeddings, same agent-config resolution as chat models); `get_embeddings_for_agent` in `utils/model.py`.
- **Shared ReAct streaming adapter** (`quantcell/agents/utils/langgraph_stream.py`): runs a LangGraph prebuilt ReAct agent via `astream(stream_mode="messages")` and maps AIMessage chunks → `streaming.message_chunk`, tool-call chunks → `tool_call_started` (deduped by id), `ToolMessage` → `tool_call_completed`, ending with `streaming.done()`. Used by Research + News agents so their `stream()` contract (StreamResponse events consumed by the A2A executor) is unchanged.
- **ResearchAgent (3c)**: `create_react_agent` with the 7 existing tools + a `search_knowledge_base` retriever tool when the knowledge base is available. Knowledge stack rewritten: `vdb.py` → `langchain_community.vectorstores.LanceDB` (same local uri, table `research_agent_knowledge_base`), `knowledge.py` → markdown/PDF ingestion via `langchain-text-splitters` + `pypdf`, preserving graceful-degradation contract (`get_knowledge()`/`get_vector_db()` return None without embeddings; insert functions no-op).
- **NewsAgent (3d)**: same ReAct pattern; `tools.py` web_search switches `Agent(model).arun` → chat-model `ainvoke` (Google search-grounding attempted via tool binding, plain invoke as fallback; Perplexity/OpenRouter path unchanged).
- **Trading composers (3e)**: `LlmComposer._call_llm` and `GridParamAdvisor.advise` switch AgnoAgent+output_schema → chat model `ainvoke` + fence-stripping JSON parse into the same Pydantic models, preserving validation-failure fallbacks. `adapters/assets/manager.py` fallback ticker search uses the chat model directly. New `utils/model.py` helpers: `create_chat_model_with_provider`, `get_chat_model(env_key)`.
- **Agno removal**: delete `adapters/models/factory.py` (Agno) and Agno helpers in `utils/model.py`; rewrite `adapters/models/__init__.py` around the LangChain factory; `uv remove agno`; `uv add langchain-community langchain-text-splitters lancedb pypdf` (lancedb becomes a direct dep — it previously arrived via `agno[lancedb]`).

**Tech Stack:** langgraph prebuilt ReAct, langchain-community LanceDB, langchain-text-splitters, pypdf, pytest fakes (tool-calling fake chat model with `bind_tools` returning self).

**Spec:** `docs/superpowers/specs/2026-09-07-quantcell-rebuild-design.md` (Phase 3)

## Global Constraints

- `BaseAgent.stream()` yield contract frozen (streaming.* responses; A2A executor untouched).
- Graceful degradation frozen: no embeddings → knowledge disabled, agent runs tools-only; no model → clear error yields.
- After Task 6, `grep -rn "agno" python/quantcell --include='*.py'` returns nothing (comments included) and `agno` is absent from pyproject/uv.lock.
- No network in tests.

---

### Task 1: Embeddings factory (TDD)
- [x] Failing tests in `quantcell/tests/test_langchain_factory.py`: builders per provider family return right classes with base_url/api key wiring; agent resolution honors `embedding_model` config and falls back like the Agno `create_embedder_for_agent`.
- [x] Implement `build_embeddings` + `LangChainModelFactory.create_embeddings_for_agent` + `utils/model.py:get_embeddings_for_agent`.
- [x] Commit `feat: langchain embeddings factory`.

### Task 2: Research knowledge stack (TDD)
- [x] `uv add langchain-community langchain-text-splitters lancedb pypdf`.
- [x] Rewrite `vdb.py` (LangChain LanceDB, None-graceful) and `knowledge.py` (KnowledgeBase wrapper: add_markdown_file/add_pdf_url/search; insert_* wrappers preserved).
- [x] Rewrite `research_agent/tests/test_fault_tolerance.py` for the new seams; PASS.
- [x] Commit `feat: migrate research knowledge base to langchain lancedb`.

### Task 3: ResearchAgent → LangGraph ReAct (TDD)
- [x] Shared adapter `agents/utils/langgraph_stream.py` + tests (fake tool-calling model: content chunks, tool call start/complete mapping, done).
- [x] Rewrite `research_agent/core.py`: react agent, knowledge tool conditional, `sources.py` web_search → chat `ainvoke`.
- [x] Commit `feat: migrate research agent to langgraph react`.

### Task 4: NewsAgent → LangGraph ReAct
- [x] Rewrite `news_agent/core.py` (stream/run/get_capabilities preserved) + `tools.py` web_search.
- [x] Commit `feat: migrate news agent to langgraph`.

### Task 5: Trading composers + assets fallback
- [x] `utils/model.py`: `create_chat_model_with_provider`, `get_chat_model`.
- [x] `prompt_based/composer.py` `_call_llm` → ainvoke + JSON parse to `TradePlanProposal` (timeout + failure fallback preserved); `grid_composer/llm_param_advisor.py` likewise for `GridParamAdvice`; `adapters/assets/manager.py` fallback search → chat model invoke.
- [x] Commit `feat: migrate trading llm composers and asset search to langchain`.

### Task 6: Remove Agno
- [x] Delete Agno factory (`adapters/models/factory.py`), Agno helpers in `utils/model.py`; rewrite `adapters/models/__init__.py`; fix `core/constants.py` comment; sweep remaining imports.
- [x] `cd python && uv remove agno`.
- [x] Full suite green; `import quantcell.server.main` clean; agno grep empty.
- [x] Commit `feat: remove agno dependency` + push.

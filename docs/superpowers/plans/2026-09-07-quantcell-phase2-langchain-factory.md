# QuantCell Phase 2: LangChain Model Factory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a LangChain-based chat-model factory alongside the existing Agno factory so Phase 3 agents can consume LangChain models, with zero change to existing Agno agents.

**Architecture:** New module `quantcell/adapters/models/langchain_factory.py` mirrors the structure of `factory.py` (provider builders + factory + convenience functions) but returns LangChain `BaseChatModel` instances. It reuses the same `ConfigManager` (three-tier config, per-agent YAML, fallback chains). `utils/model.py` gains `get_chat_model_for_agent()` and `chat_model_should_use_json_mode()` next to their Agno counterparts. Embedders stay Agno-based until Phase 3 (coupled to LanceDB knowledge rewrite).

**Tech Stack:** langchain-openai, langchain-google-genai, langchain-ollama; uv; pytest.

**Spec:** `docs/superpowers/specs/2026-09-07-quantcell-rebuild-design.md` (Phase 2)

## Global Constraints

- Do NOT modify `factory.py` behavior or remove Agno; both factories coexist until Phase 3 completes.
- No network calls in tests; inject `ConfigManager`/`ProviderConfig` fakes.
- Provider coverage: openai, google, azure, ollama, openrouter, siliconflow, deepseek, dashscope, openai-compatible (9 total; the last five build on `ChatOpenAI` with `base_url`).

---

### Task 1: Dependencies

- [ ] **Step 1:** `cd python && uv add langchain-openai langchain-google-genai langchain-ollama`
- [ ] **Step 2:** Verify import: `uv run python -c "from langchain_openai import ChatOpenAI, AzureChatOpenAI; from langchain_google_genai import ChatGoogleGenerativeAI; from langchain_ollama import ChatOllama; print('ok')"`
- [ ] **Step 3:** Commit: `git add pyproject.toml uv.lock && git commit -m "feat: add langchain provider dependencies"`

### Task 2: Provider builders (TDD)

**Files:**
- Create: `python/quantcell/adapters/models/langchain_factory.py`
- Test: `python/quantcell/tests/test_langchain_factory.py`

**Interfaces:**
- Produces: `build_chat_model(provider: str, config: ProviderConfig, model_id: str | None, **params) -> BaseChatModel`; registry `LC_PROVIDER_BUILDERS: dict[str, Callable]` keyed by the 9 provider names.

- [ ] **Step 1:** Write failing tests: one per provider asserting returned class and key attrs (`model_name`/`model`, `base_url`, azure deployment/api_version), using hand-built `ProviderConfig` objects. Include: unknown provider raises `ValueError`; `model_id=None` falls back to `config.default_model`; provider params merge with call kwargs (kwargs win).
- [ ] **Step 2:** Run: `uv run pytest quantcell/tests/test_langchain_factory.py -v` → FAIL (module missing).
- [ ] **Step 3:** Implement builders: `ChatOpenAI` (openai + the 5 compatible providers, each with its config `base_url`), `AzureChatOpenAI` (deployment name = model_id, `azure_endpoint`, `api_version` from `extra_config`), `ChatGoogleGenerativeAI`, `ChatOllama` (base_url from `parameters["host"]`).
- [ ] **Step 4:** Run tests → PASS.
- [ ] **Step 5:** Commit: `git commit -am "feat: langchain chat model builders for all 9 providers"`

### Task 3: Factory with agent resolution + fallback (TDD)

**Files:**
- Modify: `python/quantcell/adapters/models/langchain_factory.py`
- Test: `python/quantcell/tests/test_langchain_factory.py`

**Interfaces:**
- Produces: `LangChainModelFactory(config_manager=None)` with `create_chat_model(model_id=None, provider=None, use_fallback=True, provider_models=None, **kwargs)` and `create_chat_model_for_agent(agent_name, **kwargs)`; module-level singletons `get_langchain_model_factory()`, `create_chat_model()`, `create_chat_model_for_agent()` mirroring `factory.py`.

- [ ] **Step 1:** Write failing tests with a stub ConfigManager: primary-provider selection; agent YAML resolution (provider+model_id from agent config); unavailable configured provider falls back to primary with `provider_models` mapping honored; fallback chain tried in order on builder failure; all-fail raises `ValueError`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement, mirroring `ModelFactory.create_model` / `create_model_for_agent` resolution logic (validate via `config_manager.validate_provider`, same priority rules).
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit: `git commit -am "feat: langchain model factory with agent config and fallback"`

### Task 4: utils/model.py helpers (TDD)

**Files:**
- Modify: `python/quantcell/utils/model.py`
- Test: `python/quantcell/tests/test_langchain_model_utils.py`

**Interfaces:**
- Produces: `get_chat_model_for_agent(agent_name, **kwargs)`, `chat_model_should_use_json_mode(model) -> bool`, `describe_chat_model(model) -> str`.

- [ ] **Step 1:** Failing tests: `chat_model_should_use_json_mode` returns True for `ChatGoogleGenerativeAI`, True for `ChatOpenAI` with non-OpenAI `base_url` (deepseek/openrouter/etc.), True for plain OpenAI (mirrors Agno helper), False for `ChatOllama` (local models use prompt-based JSON); `describe_chat_model` formats "model (via provider-class)".
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit: `git commit -am "feat: langchain model helpers in utils"`

### Task 5: Full verification + push

- [ ] **Step 1:** `uv run pytest -q` full suite → 401 pre-existing + new tests all pass.
- [ ] **Step 2:** `git push`

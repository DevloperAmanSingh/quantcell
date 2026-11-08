# QuantCell Rebuild Design

**Status:** Approved in chat (2026-09-07)

## Goal

Turn the upstream fork into QuantCell: a multi-agent financial platform owned by this repo's author, with LangGraph replacing Agno for all LLM agents, a trimmed exchange surface, rewritten prompts, and a fresh repo identity.

## Decisions (approved)

1. **Framework:** Replace Agno with **LangGraph** in the 5 LLM agents (Super Agent, Planner, ResearchAgent, NewsAgent, PromptStrategyAgent). Motivations: learning a high-demand framework and visible divergence from upstream.
2. **Core scope:** Keep the orchestration core unchanged: `AgentOrchestrator`, TaskExecutor, event router/buffer, conversation stores, and the A2A protocol boundary (`a2a-sdk`). Only agent internals change. The `BaseAgent.stream()` async-generator contract is frozen.
3. **Repo identity:** Fresh git history, project renamed **QuantCell**. Apache 2.0 LICENSE retained with a NOTICE file crediting upstream for derived code (required by Apache 2.0).
4. **Exchanges:** Live trading trimmed to **Binance and Coinbase** (both via ccxt). Paper trading kept behind the same execution interface. OKX/Hyperliquid/Gate/MEXC-specific code and the `python-okx` dependency removed.
5. **Prompts:** All agent/planner/super-agent prompts rewritten in our own voice.
6. **Docs:** Single English README telling the QuantCell architecture story; multilingual READMEs deleted.

## Phases

1. **Repo identity & branding** (this phase has its own plan): history reset, `upstream` → `quantcell` rename, Tauri/frontend rebrand, LICENSE/NOTICE, new README.
2. **Model factory → LangChain chat models** (`init_chat_model`), preserving multi-provider config.
3. **Agent migration:** Super Agent → Planner (LangGraph `interrupt()` bridged to the existing `UserInputRequest`/`asyncio.Event` HITL flow) → ResearchAgent (ReAct + LanceDB retriever tool) → NewsAgent → PromptStrategyAgent. Remove `agno` dependency.
4. **Exchange trim** to Binance + Coinbase.
5. **Prompt rewrite + opportunistic fixes** (e.g., replace the orchestrator's 100 ms polling loop with `asyncio.Event`).
6. **README/docs refresh.**

## Constraints

- Existing pytest suites must pass after every phase.
- No change to the A2A wire behavior or the SSE contract consumed by the frontend.
- LanceDB stays as the vector store; SQLite stays as the app store.

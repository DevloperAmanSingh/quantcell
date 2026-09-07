"""LangGraph ReAct implementation of the Research Agent.

The agent researches from primary sources: SEC/EDGAR filings, A-share
disclosures, web search, and crypto project data. When embeddings are
configured, previously ingested filings are searchable through a
`search_knowledge_base` tool backed by the local LanceDB store; without
embeddings the agent runs in tools-only mode (graceful degradation).
"""

import json
import os
from typing import AsyncGenerator, Dict, Optional

from edgar import set_identity
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import create_react_agent
from loguru import logger

import quantcell.utils.model as model_utils_mod
from quantcell.agents.research_agent.knowledge import KnowledgeBase, get_knowledge
from quantcell.agents.research_agent.prompts import (
    KNOWLEDGE_AGENT_EXPECTED_OUTPUT,
    KNOWLEDGE_AGENT_INSTRUCTION,
)
from quantcell.agents.research_agent.sources import (
    fetch_ashare_filings,
    fetch_event_sec_filings,
    fetch_periodic_sec_filings,
    search_crypto_people,
    search_crypto_projects,
    search_crypto_vcs,
    web_search,
)
from quantcell.agents.utils.context import build_ctx_from_dep
from quantcell.agents.utils.langgraph_stream import stream_react_agent
from quantcell.core.types import BaseAgent, StreamResponse


def make_knowledge_search_tool(knowledge: KnowledgeBase):
    """Expose the knowledge base as a plain tool function for the ReAct agent."""

    def search_knowledge_base(query: str) -> str:
        """Search the internal research knowledge base of previously ingested
        SEC filings and documents for passages relevant to the query.

        Args:
            query: Natural-language search query.

        Returns:
            Relevant document excerpts, or a note when nothing matches.
        """
        docs = knowledge.search(query)
        if not docs:
            return "No matching documents in the knowledge base."
        return "\n\n---\n\n".join(doc.page_content for doc in docs)

    return search_knowledge_base


class ResearchAgent(BaseAgent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        tools = [
            fetch_periodic_sec_filings,
            fetch_event_sec_filings,
            fetch_ashare_filings,
            web_search,
            search_crypto_projects,
            search_crypto_vcs,
            search_crypto_people,
        ]
        # Lazily obtain knowledge; expose the search tool only when available
        self.knowledge = get_knowledge()
        if self.knowledge is not None:
            tools.append(make_knowledge_search_tool(self.knowledge))
        self.tools = tools

        model = model_utils_mod.get_chat_model_for_agent("research_agent")
        self.graph = create_react_agent(
            model,
            tools,
            prompt=(
                KNOWLEDGE_AGENT_INSTRUCTION + "\n" + KNOWLEDGE_AGENT_EXPECTED_OUTPUT
            ),
            checkpointer=InMemorySaver(),
        )

        # Configure EDGAR identity only when SEC_EMAIL is present
        sec_email = os.getenv("SEC_EMAIL")
        if sec_email:
            set_identity(sec_email)
        else:
            logger.warning(
                "SEC_EMAIL not set; EDGAR identity is not configured for ResearchAgent."
            )

    async def stream(
        self,
        query: str,
        conversation_id: str,
        task_id: str,
        dependencies: Optional[Dict] = None,
    ) -> AsyncGenerator[StreamResponse, None]:
        context = build_ctx_from_dep(dependencies)
        if context:
            query = f"{query}\n\n<context>\n{json.dumps(context)}\n</context>"

        config = {"configurable": {"thread_id": conversation_id}}
        async for response in stream_react_agent(
            self.graph, [HumanMessage(content=query)], config
        ):
            yield response
        logger.info("Financial data analysis completed")

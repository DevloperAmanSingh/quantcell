"""News Agent Core Implementation (LangGraph ReAct)."""

from typing import Any, AsyncGenerator, Dict, Optional

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import create_react_agent
from loguru import logger

import quantcell.utils.model as model_utils_mod
from quantcell.agents.utils.langgraph_stream import stream_react_agent
from quantcell.config.manager import get_config_manager
from quantcell.core.types import BaseAgent, StreamResponse

from .prompts import NEWS_AGENT_INSTRUCTIONS
from .tools import get_breaking_news, get_financial_news, web_search


class NewsAgent(BaseAgent):
    """News Agent for fetching and analyzing news."""

    def __init__(self, **kwargs):
        """Initialize the News Agent."""
        super().__init__(**kwargs)
        # Load agent configuration
        self.config_manager = get_config_manager()
        self.agent_config = self.config_manager.get_agent_config("news_agent")

        self.tools = [web_search, get_breaking_news, get_financial_news]
        model = model_utils_mod.get_chat_model_for_agent("news_agent")
        self.graph = create_react_agent(
            model,
            self.tools,
            prompt="\n".join(NEWS_AGENT_INSTRUCTIONS)
            if isinstance(NEWS_AGENT_INSTRUCTIONS, (list, tuple))
            else NEWS_AGENT_INSTRUCTIONS,
            checkpointer=InMemorySaver(),
        )

        logger.info("NewsAgent initialized with news tools")

    async def stream(
        self,
        query: str,
        conversation_id: str,
        task_id: str,
        dependencies: Optional[Dict] = None,
    ) -> AsyncGenerator[StreamResponse, None]:
        """Stream news responses."""
        logger.info(
            f"Processing news query: {query[:100]}{'...' if len(query) > 100 else ''}"
        )
        config = {"configurable": {"thread_id": conversation_id}}
        async for response in stream_react_agent(
            self.graph, [HumanMessage(content=query)], config
        ):
            yield response
        logger.info("News query processed successfully")

    async def run(self, query: str, **kwargs) -> str:
        """Run news agent and return the final response text."""
        logger.info(
            f"Running news agent with query: {query[:100]}{'...' if len(query) > 100 else ''}"
        )
        try:
            result = await self.graph.ainvoke(
                {"messages": [HumanMessage(content=query)]},
                {"configurable": {"thread_id": "news-agent-run"}},
            )
            final = result["messages"][-1]
            return str(final.content)
        except Exception as e:
            logger.error(f"Error in NewsAgent run: {e}")
            return f"Error processing news query: {str(e)}"

    def get_capabilities(self) -> Dict[str, Any]:
        """Get agent capabilities."""
        return {
            "name": "News Agent",
            "description": "Professional news agent for fetching and analyzing news",
            "tools": [
                {
                    "name": "web_search",
                    "description": "Search for general news and information",
                },
                {
                    "name": "get_breaking_news",
                    "description": "Get latest breaking news",
                },
                {
                    "name": "get_financial_news",
                    "description": "Get financial and market news",
                },
            ],
            "supported_queries": [
                "Latest news",
                "Breaking news",
                "Financial news",
                "Market updates",
                "Topic-specific news search",
            ],
        }

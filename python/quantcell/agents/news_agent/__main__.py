import asyncio

from quantcell.agents.news_agent import NewsAgent
from quantcell.core import create_wrapped_agent

if __name__ == "__main__":
    agent = create_wrapped_agent(NewsAgent)
    asyncio.run(agent.serve())

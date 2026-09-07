"""
Model adapters - LangChain chat model and embeddings creation.

This module provides the model factory for creating LangChain model instances
using the three-tier configuration system (YAML + .env + environment variables).

Usage:
    >>> from quantcell.adapters.models import create_chat_model, create_chat_model_for_agent

    >>> # Create chat model with default provider
    >>> model = create_chat_model()

    >>> # Create chat model for specific agent
    >>> model = create_chat_model_for_agent("research_agent")

Prefer the helpers in `quantcell.utils.model` (get_chat_model_for_agent,
get_embeddings_for_agent, ...) for agent code; they add logging and error
context on top of these factory functions.
"""

from quantcell.adapters.models.langchain_factory import (
    LangChainModelFactory,
    build_chat_model,
    build_embeddings,
    create_chat_model,
    create_chat_model_for_agent,
    create_embeddings_for_agent,
    get_langchain_model_factory,
)

__all__ = [
    "LangChainModelFactory",
    "build_chat_model",
    "build_embeddings",
    "create_chat_model",
    "create_chat_model_for_agent",
    "create_embeddings_for_agent",
    "get_langchain_model_factory",
]

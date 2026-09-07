"""Model utility functions using the centralized configuration system.

This module provides convenient functions to create LangChain chat models and
embeddings using the three-tier configuration system (YAML + .env +
environment variables). All agents and services resolve their models through
these helpers, which add logging and error context on top of
`quantcell.adapters.models.langchain_factory`.
"""

import os
from typing import Optional

from loguru import logger


def describe_chat_model(model) -> str:
    """Human-readable description of a LangChain chat model."""
    try:
        model_id = (
            getattr(model, "model_name", None)
            or getattr(model, "model", None)
            or getattr(model, "deployment_name", None)
        )
        return f"{model_id} (via {type(model).__name__})"
    except Exception:
        return "unknown model/provider"


def chat_model_should_use_json_mode(model) -> bool:
    """
    Determine if a LangChain chat model should use JSON mode instead of
    provider-native structured outputs.

    Every hosted provider we support either requires JSON mode (Gemini,
    DeepSeek, DashScope) or is safer with it (OpenAI-compatible proxies), so
    hosted models return True. Local Ollama models return False: many local
    models lack reliable JSON mode, so prompt-based structured output is used
    instead.
    """
    try:
        from langchain_ollama import ChatOllama

        if isinstance(model, ChatOllama):
            logger.debug("Detected Ollama model - not using JSON mode")
            return False
    except ImportError:
        pass

    logger.debug(f"Using JSON mode for chat model: {describe_chat_model(model)}")
    return True


def get_chat_model_for_agent(agent_name: str, **kwargs):
    """
    Get a LangChain chat model configured for an agent (three-tier config).

    Args:
        agent_name: Agent name matching configs/agents/<agent_name>.yaml
        **kwargs: Override parameters for this call

    Returns:
        A LangChain BaseChatModel configured for the agent.
    """
    from quantcell.adapters.models.langchain_factory import (
        create_chat_model_for_agent,
    )

    try:
        return create_chat_model_for_agent(agent_name, **kwargs)
    except Exception as e:
        logger.error(
            f"Failed to create LangChain chat model for agent '{agent_name}': {e}"
        )
        raise


def get_chat_model(env_key: str, **kwargs):
    """
    Get a LangChain chat model with environment variable override.

    Uses the env var named by `env_key` for the model id when set, the primary
    provider otherwise, with the full fallback chain enabled.
    """
    from quantcell.adapters.models.langchain_factory import (
        get_langchain_model_factory,
    )

    model_id = os.getenv(env_key)
    if model_id:
        logger.debug(f"Using model_id from {env_key}: {model_id}")
    return get_langchain_model_factory().create_chat_model(
        model_id=model_id, provider=None, use_fallback=True, **kwargs
    )


def create_chat_model_with_provider(
    provider: str,
    model_id: Optional[str] = None,
    api_key: Optional[str] = None,
    **kwargs,
):
    """
    Create a LangChain chat model from a specific provider.

    Includes per-call API key override (used by trading strategies where the
    user supplies keys per strategy). No fallback: an explicit provider
    request should fail loudly.
    """
    from quantcell.adapters.models.langchain_factory import (
        build_chat_model,
        get_langchain_model_factory,
    )

    if not api_key:
        return get_langchain_model_factory().create_chat_model(
            model_id=model_id, provider=provider, use_fallback=False, **kwargs
        )

    from quantcell.config.manager import ProviderConfig, get_config_manager

    existing = get_config_manager().get_provider_config(provider)
    if not existing:
        raise ValueError(f"Provider configuration not found: {provider}")

    overridden = ProviderConfig(
        name=existing.name,
        enabled=existing.enabled,
        api_key=api_key,
        base_url=existing.base_url,
        default_model=existing.default_model,
        models=existing.models,
        parameters=existing.parameters,
        default_embedding_model=existing.default_embedding_model,
        embedding_models=existing.embedding_models,
        embedding_parameters=existing.embedding_parameters,
        extra_config=existing.extra_config,
    )
    return build_chat_model(provider, overridden, model_id, **kwargs)


def get_embeddings_for_agent(agent_name: str, **kwargs):
    """
    Get LangChain embeddings configured for an agent (three-tier config).

    Used by the research agent's knowledge base.
    """
    from quantcell.adapters.models.langchain_factory import (
        create_embeddings_for_agent,
    )

    try:
        return create_embeddings_for_agent(agent_name, **kwargs)
    except Exception as e:
        logger.error(
            f"Failed to create LangChain embeddings for agent '{agent_name}': {e}"
        )
        raise

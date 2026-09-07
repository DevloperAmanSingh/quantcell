"""
LangChain Model Factory - creates LangChain chat models from the three-tier config

Parallel to `factory.py` (the Agno factory): same ConfigManager, same provider
names, same fallback semantics, but returns LangChain `BaseChatModel` instances
for LangGraph-based agents. Both factories coexist during the Agno -> LangGraph
migration; the Agno factory is removed once the last agent has migrated.
"""

from typing import Any, Callable, Dict, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from loguru import logger

from quantcell.config.manager import ConfigManager, ProviderConfig, get_config_manager

# Providers that speak the OpenAI wire protocol and differ only by base_url.
_OPENAI_COMPATIBLE_PROVIDERS = (
    "openrouter",
    "siliconflow",
    "deepseek",
    "dashscope",
    "openai-compatible",
)


def _merged_params(config: ProviderConfig, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """Provider YAML defaults < per-call kwargs."""
    return {**config.parameters, **kwargs}


def _build_openai_family(
    provider: str, config: ProviderConfig, model_id: Optional[str], **kwargs
) -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    model_id = model_id or config.default_model
    params = _merged_params(config, kwargs)
    # `host` is an Ollama-ism that may leak through shared config; ChatOpenAI
    # rejects unknown kwargs, so pass only the parameters it understands.
    logger.info(f"Creating LangChain {provider} model: {model_id}")
    return ChatOpenAI(
        model=model_id,
        api_key=config.api_key,
        base_url=config.base_url,
        temperature=params.get("temperature"),
        max_tokens=params.get("max_tokens"),
        top_p=params.get("top_p"),
        frequency_penalty=params.get("frequency_penalty"),
        presence_penalty=params.get("presence_penalty"),
    )


def _build_azure(
    provider: str, config: ProviderConfig, model_id: Optional[str], **kwargs
) -> BaseChatModel:
    from langchain_openai import AzureChatOpenAI

    deployment_name = model_id or config.default_model
    params = _merged_params(config, kwargs)
    api_version = config.extra_config.get("api_version", "2024-10-21")
    logger.info(
        f"Creating LangChain Azure model: deployment={deployment_name}, "
        f"endpoint={config.base_url}, api_version={api_version}"
    )
    return AzureChatOpenAI(
        azure_deployment=deployment_name,
        api_key=config.api_key,
        azure_endpoint=config.base_url,
        api_version=api_version,
        temperature=params.get("temperature"),
        max_tokens=params.get("max_tokens"),
    )


def _build_google(
    provider: str, config: ProviderConfig, model_id: Optional[str], **kwargs
) -> BaseChatModel:
    from langchain_google_genai import ChatGoogleGenerativeAI

    model_id = model_id or config.default_model
    params = _merged_params(config, kwargs)
    logger.info(f"Creating LangChain Google model: {model_id}")
    return ChatGoogleGenerativeAI(
        model=model_id,
        google_api_key=config.api_key,
        temperature=params.get("temperature"),
    )


def _build_ollama(
    provider: str, config: ProviderConfig, model_id: Optional[str], **kwargs
) -> BaseChatModel:
    from langchain_ollama import ChatOllama

    model_id = model_id or config.default_model
    params = _merged_params(config, kwargs)
    logger.info(f"Creating LangChain Ollama model: {model_id}")
    return ChatOllama(
        model=model_id,
        base_url=params.get("host"),
        temperature=params.get("temperature"),
    )


LC_PROVIDER_BUILDERS: Dict[str, Callable[..., BaseChatModel]] = {
    "openai": _build_openai_family,
    **{name: _build_openai_family for name in _OPENAI_COMPATIBLE_PROVIDERS},
    "azure": _build_azure,
    "google": _build_google,
    "ollama": _build_ollama,
}


def build_chat_model(
    provider: str,
    config: ProviderConfig,
    model_id: Optional[str] = None,
    **kwargs,
) -> BaseChatModel:
    """Build a LangChain chat model for a provider from its resolved config."""
    builder = LC_PROVIDER_BUILDERS.get(provider)
    if builder is None:
        raise ValueError(f"Unsupported provider: {provider}")
    return builder(provider, config, model_id, **kwargs)


# ============================================
# Embeddings builders
# ============================================


def _require_embedding_model(
    config: ProviderConfig, model_id: Optional[str]
) -> str:
    model_id = model_id or config.default_embedding_model
    if not model_id:
        raise ValueError(
            f"Provider '{config.name}' does not support embedding models. "
            f"Please configure embedding models in providers/{config.name}.yaml"
        )
    return model_id


def _build_openai_family_embeddings(
    provider: str, config: ProviderConfig, model_id: Optional[str], **kwargs
):
    from langchain_openai import OpenAIEmbeddings

    model_id = _require_embedding_model(config, model_id)
    params = {**config.embedding_parameters, **kwargs}
    dimensions = params.get("dimensions")
    logger.info(f"Creating LangChain {provider} embeddings: {model_id}")
    return OpenAIEmbeddings(
        model=model_id,
        api_key=config.api_key,
        base_url=config.base_url,
        dimensions=int(dimensions) if dimensions else None,
        # Non-OpenAI endpoints reject OpenAI's tokenized input arrays.
        check_embedding_ctx_length=config.base_url is None,
    )


def _build_google_embeddings(
    provider: str, config: ProviderConfig, model_id: Optional[str], **kwargs
):
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    model_id = _require_embedding_model(config, model_id)
    if not model_id.startswith("models/"):
        model_id = f"models/{model_id}"
    logger.info(f"Creating LangChain Google embeddings: {model_id}")
    return GoogleGenerativeAIEmbeddings(model=model_id, google_api_key=config.api_key)


def _build_azure_embeddings(
    provider: str, config: ProviderConfig, model_id: Optional[str], **kwargs
):
    from langchain_openai import AzureOpenAIEmbeddings

    deployment = _require_embedding_model(config, model_id)
    api_version = config.extra_config.get("api_version", "2024-10-21")
    logger.info(f"Creating LangChain Azure embeddings: deployment={deployment}")
    return AzureOpenAIEmbeddings(
        azure_deployment=deployment,
        api_key=config.api_key,
        azure_endpoint=config.base_url,
        api_version=api_version,
    )


def _build_ollama_embeddings(
    provider: str, config: ProviderConfig, model_id: Optional[str], **kwargs
):
    from langchain_ollama import OllamaEmbeddings

    model_id = _require_embedding_model(config, model_id)
    params = {**config.embedding_parameters, **config.parameters, **kwargs}
    logger.info(f"Creating LangChain Ollama embeddings: {model_id}")
    return OllamaEmbeddings(model=model_id, base_url=params.get("host"))


LC_EMBEDDINGS_BUILDERS: Dict[str, Callable] = {
    "openai": _build_openai_family_embeddings,
    **{name: _build_openai_family_embeddings for name in _OPENAI_COMPATIBLE_PROVIDERS},
    "azure": _build_azure_embeddings,
    "google": _build_google_embeddings,
    "ollama": _build_ollama_embeddings,
}


def build_embeddings(
    provider: str,
    config: ProviderConfig,
    model_id: Optional[str] = None,
    **kwargs,
):
    """Build a LangChain embeddings instance for a provider."""
    builder = LC_EMBEDDINGS_BUILDERS.get(provider)
    if builder is None:
        raise ValueError(f"Unsupported provider: {provider}")
    return builder(provider, config, model_id, **kwargs)


class LangChainModelFactory:
    """Creates LangChain chat models with the same resolution rules as ModelFactory.

    Mirrors `ModelFactory` (Agno): three-tier configuration, per-agent YAML
    resolution, provider validation, and fallback-provider chains.
    """

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        self.config_manager = config_manager or get_config_manager()

    def create_chat_model(
        self,
        model_id: Optional[str] = None,
        provider: Optional[str] = None,
        use_fallback: bool = True,
        provider_models: Optional[dict] = None,
        **kwargs,
    ) -> BaseChatModel:
        """Create a chat model, trying fallback providers on failure."""
        provider = provider or self.config_manager.primary_provider
        provider_models = provider_models or {}

        try:
            return self._create_internal(model_id, provider, **kwargs)
        except Exception as e:
            logger.warning(f"Failed to create chat model with provider {provider}: {e}")
            if not use_fallback:
                raise

            for fallback in self.config_manager.fallback_providers:
                if fallback == provider:
                    continue
                fallback_model_id = provider_models.get(fallback)
                if fallback_model_id is None:
                    fallback_config = self.config_manager.get_provider_config(fallback)
                    fallback_model_id = (
                        fallback_config.default_model if fallback_config else model_id
                    )
                try:
                    logger.info(f"Trying fallback provider: {fallback}")
                    return self._create_internal(fallback_model_id, fallback, **kwargs)
                except Exception as fallback_error:
                    logger.warning(
                        f"Fallback provider {fallback} also failed: {fallback_error}"
                    )
                    continue

            raise ValueError(
                f"Failed to create chat model. Primary provider ({provider}) "
                f"and all fallback providers failed. Original error: {e}"
            )

    def create_chat_model_for_agent(
        self, agent_name: str, use_fallback: bool = True, **kwargs
    ) -> BaseChatModel:
        """Create a chat model from an agent's YAML config (three-tier resolved)."""
        agent_config = self.config_manager.get_agent_config(agent_name)
        if not agent_config:
            raise ValueError(f"Agent configuration not found: {agent_name}")
        if not agent_config.enabled:
            raise ValueError(f"Agent is disabled: {agent_name}")

        model_config = agent_config.primary_model
        merged_params = {**model_config.parameters, **kwargs}
        provider = model_config.provider
        model_id = model_config.model_id

        is_valid, error_msg = self.config_manager.validate_provider(provider)
        if not is_valid:
            # Same rule as the Agno factory: fall back to the primary provider,
            # honoring the agent's provider-specific model mapping.
            fallback_provider = self.config_manager.primary_provider
            logger.warning(
                f"Configured provider '{provider}' for agent '{agent_name}' is not "
                f"available: {error_msg}. Falling back to: {fallback_provider}"
            )
            provider = fallback_provider
            if fallback_provider in model_config.provider_models:
                model_id = model_config.provider_models[fallback_provider]
            else:
                provider_config = self.config_manager.get_provider_config(
                    fallback_provider
                )
                if provider_config:
                    model_id = provider_config.default_model

        logger.info(
            f"Creating LangChain chat model for agent '{agent_name}': "
            f"model_id={model_id}, provider={provider}"
        )
        return self.create_chat_model(
            model_id=model_id,
            provider=provider,
            use_fallback=use_fallback,
            provider_models=model_config.provider_models,
            **merged_params,
        )

    def create_embeddings_for_agent(self, agent_name: str, **kwargs):
        """Create LangChain embeddings from an agent's config.

        Mirrors the Agno `create_embedder_for_agent` rules: prefer the agent's
        `embedding_model` config; fall back to the primary provider's default
        embedding model when the configured provider is unavailable or no
        embedding config exists.
        """
        agent_config = self.config_manager.get_agent_config(agent_name)
        if not agent_config:
            raise ValueError(f"Agent configuration not found: {agent_name}")
        if not agent_config.enabled:
            raise ValueError(f"Agent is disabled: {agent_name}")

        if agent_config.embedding_model:
            emb = agent_config.embedding_model
            provider, model_id = emb.provider, emb.model_id
            merged_params = {**emb.parameters, **kwargs}
            is_valid, error_msg = self.config_manager.validate_provider(provider)
            if not is_valid:
                fallback = self.config_manager.primary_provider
                logger.warning(
                    f"Embedding provider '{provider}' for agent '{agent_name}' "
                    f"unavailable: {error_msg}. Falling back to: {fallback}"
                )
                provider = fallback
                if fallback in (emb.provider_models or {}):
                    model_id = emb.provider_models[fallback]
                else:
                    provider_config = self.config_manager.get_provider_config(fallback)
                    model_id = (
                        provider_config.default_embedding_model
                        if provider_config
                        else None
                    )
        else:
            provider = agent_config.primary_model.provider
            model_id = None  # use provider default embedding model
            merged_params = dict(kwargs)
            is_valid, _ = self.config_manager.validate_provider(provider)
            if not is_valid:
                provider = self.config_manager.primary_provider

        provider_config = self.config_manager.get_provider_config(provider)
        if not provider_config:
            raise ValueError(f"Provider configuration not found: {provider}")
        is_valid, error_msg = self.config_manager.validate_provider(provider)
        if not is_valid:
            raise ValueError(f"Provider validation failed: {error_msg}")
        return build_embeddings(provider, provider_config, model_id, **merged_params)

    def _create_internal(
        self, model_id: Optional[str], provider: str, **kwargs
    ) -> BaseChatModel:
        if provider not in LC_PROVIDER_BUILDERS:
            raise ValueError(f"Unsupported provider: {provider}")

        provider_config = self.config_manager.get_provider_config(provider)
        if not provider_config:
            raise ValueError(f"Provider configuration not found: {provider}")

        is_valid, error_msg = self.config_manager.validate_provider(provider)
        if not is_valid:
            raise ValueError(f"Provider validation failed: {error_msg}")

        return build_chat_model(provider, provider_config, model_id, **kwargs)


# ============================================
# Singleton and Convenience Functions
# ============================================

_langchain_factory: Optional[LangChainModelFactory] = None


def get_langchain_model_factory() -> LangChainModelFactory:
    """Get singleton LangChain model factory instance."""
    global _langchain_factory
    if _langchain_factory is None:
        _langchain_factory = LangChainModelFactory()
    return _langchain_factory


def create_chat_model(
    model_id: Optional[str] = None, provider: Optional[str] = None, **kwargs
) -> BaseChatModel:
    """Convenience function to create a LangChain chat model."""
    return get_langchain_model_factory().create_chat_model(model_id, provider, **kwargs)


def create_chat_model_for_agent(agent_name: str, **kwargs) -> BaseChatModel:
    """Convenience function to create a LangChain chat model for an agent."""
    return get_langchain_model_factory().create_chat_model_for_agent(
        agent_name, **kwargs
    )


def create_embeddings_for_agent(agent_name: str, **kwargs):
    """Convenience function to create LangChain embeddings for an agent."""
    return get_langchain_model_factory().create_embeddings_for_agent(
        agent_name, **kwargs
    )

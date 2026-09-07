"""Tests for the LangChain chat-model factory (Phase 2).

These tests build ProviderConfig objects by hand and never touch the network:
LangChain chat model constructors only validate/wire parameters.
"""

from typing import Any

import pytest
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langchain_openai import AzureChatOpenAI, ChatOpenAI

from quantcell.adapters.models.langchain_factory import (
    LC_PROVIDER_BUILDERS,
    build_chat_model,
)
from quantcell.config.manager import ProviderConfig


def make_config(name: str, **overrides) -> ProviderConfig:
    defaults: dict[str, Any] = dict(
        name=name,
        enabled=True,
        api_key="test-key",
        base_url=None,
        default_model="default-model",
        models=[],
        parameters={},
    )
    defaults.update(overrides)
    return ProviderConfig(**defaults)


class TestBuilderRegistry:
    def test_all_nine_providers_registered(self):
        expected = {
            "openai",
            "google",
            "azure",
            "ollama",
            "openrouter",
            "siliconflow",
            "deepseek",
            "dashscope",
            "openai-compatible",
        }
        assert expected == set(LC_PROVIDER_BUILDERS.keys())

    def test_unknown_provider_raises(self):
        config = make_config("nope")
        with pytest.raises(ValueError, match="Unsupported provider"):
            build_chat_model("nope", config, None)


class TestOpenAIFamilyBuilders:
    def test_openai(self):
        config = make_config("openai", default_model="gpt-4o")
        model = build_chat_model("openai", config, None)
        assert isinstance(model, ChatOpenAI)
        assert model.model_name == "gpt-4o"

    @pytest.mark.parametrize(
        "provider,base_url",
        [
            ("openrouter", "https://openrouter.ai/api/v1"),
            ("siliconflow", "https://api.siliconflow.cn/v1"),
            ("deepseek", "https://api.deepseek.com"),
            ("dashscope", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            ("openai-compatible", "http://localhost:8000/v1"),
        ],
    )
    def test_compatible_providers_use_chatopenai_with_base_url(
        self, provider, base_url
    ):
        config = make_config(provider, base_url=base_url, default_model="some-model")
        model = build_chat_model(provider, config, None)
        assert isinstance(model, ChatOpenAI)
        assert model.openai_api_base == base_url
        assert model.model_name == "some-model"

    def test_explicit_model_id_overrides_default(self):
        config = make_config("openai", default_model="gpt-4o")
        model = build_chat_model("openai", config, "gpt-4o-mini")
        assert model.model_name == "gpt-4o-mini"

    def test_call_kwargs_override_config_parameters(self):
        config = make_config(
            "openai", default_model="gpt-4o", parameters={"temperature": 0.2}
        )
        model = build_chat_model("openai", config, None, temperature=0.9)
        assert model.temperature == 0.9

    def test_config_parameters_apply_when_no_kwargs(self):
        config = make_config(
            "openai", default_model="gpt-4o", parameters={"temperature": 0.2}
        )
        model = build_chat_model("openai", config, None)
        assert model.temperature == 0.2


class TestAzureBuilder:
    def test_azure_uses_deployment_and_endpoint(self):
        config = make_config(
            "azure",
            base_url="https://myres.openai.azure.com",
            default_model="my-deployment",
            extra_config={"api_version": "2024-10-21"},
        )
        model = build_chat_model("azure", config, None)
        assert isinstance(model, AzureChatOpenAI)
        assert model.deployment_name == "my-deployment"
        assert model.openai_api_version == "2024-10-21"


class TestGoogleBuilder:
    def test_google(self):
        config = make_config("google", default_model="gemini-2.5-flash")
        model = build_chat_model("google", config, None)
        assert isinstance(model, ChatGoogleGenerativeAI)
        assert model.model == "gemini-2.5-flash"


class TestOllamaBuilder:
    def test_ollama_uses_host_parameter(self):
        config = make_config(
            "ollama",
            api_key=None,
            default_model="llama3.1",
            parameters={"host": "http://localhost:11434"},
        )
        model = build_chat_model("ollama", config, None)
        assert isinstance(model, ChatOllama)
        assert model.model == "llama3.1"
        assert model.base_url == "http://localhost:11434"


# ============================================
# Factory-level tests (agent resolution + fallback)
# ============================================

from quantcell.adapters.models.langchain_factory import (  # noqa: E402
    LangChainModelFactory,
)
from quantcell.config.manager import AgentConfig, AgentModelConfig  # noqa: E402


class StubConfigManager:
    """Minimal ConfigManager double for factory resolution tests."""

    def __init__(
        self,
        providers: dict[str, ProviderConfig],
        primary_provider: str = "openai",
        fallback_providers: list[str] | None = None,
        agents: dict[str, AgentConfig] | None = None,
        invalid_providers: set[str] | None = None,
    ):
        self._providers = providers
        self.primary_provider = primary_provider
        self.fallback_providers = fallback_providers or []
        self._agents = agents or {}
        self._invalid = invalid_providers or set()

    def get_provider_config(self, name):
        return self._providers.get(name)

    def validate_provider(self, name):
        if name in self._invalid:
            return False, f"no API key for {name}"
        if name not in self._providers:
            return False, f"unknown provider {name}"
        return True, None

    def get_agent_config(self, name):
        return self._agents.get(name)


def make_agent_config(
    name: str, provider: str, model_id: str, provider_models=None
) -> AgentConfig:
    return AgentConfig(
        name=name,
        enabled=True,
        primary_model=AgentModelConfig(
            model_id=model_id,
            provider=provider,
            parameters={},
            provider_models=provider_models,
        ),
        embedding_model=None,
        api_keys={},
        capabilities={},
        extra_config={},
    )


class TestFactoryResolution:
    def test_uses_primary_provider_by_default(self):
        cm = StubConfigManager(
            providers={"openai": make_config("openai", default_model="gpt-4o")},
            primary_provider="openai",
        )
        model = LangChainModelFactory(cm).create_chat_model()
        assert isinstance(model, ChatOpenAI)
        assert model.model_name == "gpt-4o"

    def test_agent_config_selects_provider_and_model(self):
        cm = StubConfigManager(
            providers={
                "openai": make_config("openai", default_model="gpt-4o"),
                "google": make_config("google", default_model="gemini-2.5-flash"),
            },
            primary_provider="openai",
            agents={
                "research_agent": make_agent_config(
                    "research_agent", "google", "gemini-2.5-pro"
                )
            },
        )
        model = LangChainModelFactory(cm).create_chat_model_for_agent("research_agent")
        assert isinstance(model, ChatGoogleGenerativeAI)
        assert model.model == "gemini-2.5-pro"

    def test_unavailable_agent_provider_falls_back_to_primary(self):
        cm = StubConfigManager(
            providers={
                "openai": make_config("openai", default_model="gpt-4o"),
                "google": make_config("google", default_model="gemini-2.5-flash"),
            },
            primary_provider="openai",
            invalid_providers={"google"},
            agents={
                "news_agent": make_agent_config(
                    "news_agent",
                    "google",
                    "gemini-2.5-pro",
                    provider_models={"openai": "gpt-4o-mini"},
                )
            },
        )
        model = LangChainModelFactory(cm).create_chat_model_for_agent("news_agent")
        assert isinstance(model, ChatOpenAI)
        # provider_models mapping for the fallback provider must win
        assert model.model_name == "gpt-4o-mini"

    def test_fallback_chain_on_provider_failure(self):
        cm = StubConfigManager(
            providers={
                "openai": make_config("openai", default_model="gpt-4o"),
                "ollama": make_config(
                    "ollama",
                    api_key=None,
                    default_model="llama3.1",
                    parameters={"host": "http://localhost:11434"},
                ),
            },
            primary_provider="openai",
            fallback_providers=["ollama"],
            invalid_providers={"openai"},
        )
        model = LangChainModelFactory(cm).create_chat_model()
        assert isinstance(model, ChatOllama)
        assert model.model == "llama3.1"

    def test_all_providers_failing_raises(self):
        cm = StubConfigManager(
            providers={"openai": make_config("openai", default_model="gpt-4o")},
            primary_provider="openai",
            fallback_providers=[],
            invalid_providers={"openai"},
        )
        with pytest.raises(ValueError, match="all fallback providers failed"):
            LangChainModelFactory(cm).create_chat_model()

    def test_no_fallback_reraises_original_error(self):
        cm = StubConfigManager(
            providers={"openai": make_config("openai", default_model="gpt-4o")},
            primary_provider="openai",
            invalid_providers={"openai"},
        )
        with pytest.raises(ValueError, match="validation failed"):
            LangChainModelFactory(cm).create_chat_model(use_fallback=False)

    def test_unknown_agent_raises(self):
        cm = StubConfigManager(
            providers={"openai": make_config("openai", default_model="gpt-4o")}
        )
        with pytest.raises(ValueError, match="Agent configuration not found"):
            LangChainModelFactory(cm).create_chat_model_for_agent("ghost_agent")


# ============================================
# Embeddings factory tests
# ============================================

from langchain_google_genai import GoogleGenerativeAIEmbeddings  # noqa: E402
from langchain_ollama import OllamaEmbeddings  # noqa: E402
from langchain_openai import AzureOpenAIEmbeddings, OpenAIEmbeddings  # noqa: E402

from quantcell.adapters.models.langchain_factory import (  # noqa: E402
    build_embeddings,
)


class TestEmbeddingsBuilders:
    def test_openai_embeddings(self):
        config = make_config(
            "openai", default_embedding_model="text-embedding-3-small"
        )
        emb = build_embeddings("openai", config, None)
        assert isinstance(emb, OpenAIEmbeddings)
        assert emb.model == "text-embedding-3-small"

    def test_compatible_provider_uses_base_url_and_disables_ctx_check(self):
        config = make_config(
            "siliconflow",
            base_url="https://api.siliconflow.cn/v1",
            default_embedding_model="BAAI/bge-m3",
        )
        emb = build_embeddings("siliconflow", config, None)
        assert isinstance(emb, OpenAIEmbeddings)
        assert emb.openai_api_base == "https://api.siliconflow.cn/v1"
        # Non-OpenAI endpoints reject tokenized input arrays
        assert emb.check_embedding_ctx_length is False

    def test_google_embeddings_prefixes_model(self):
        config = make_config(
            "google", default_embedding_model="gemini-embedding-001"
        )
        emb = build_embeddings("google", config, None)
        assert isinstance(emb, GoogleGenerativeAIEmbeddings)
        assert emb.model == "models/gemini-embedding-001"

    def test_azure_embeddings(self):
        config = make_config(
            "azure",
            base_url="https://myres.openai.azure.com",
            default_embedding_model="embed-deployment",
            extra_config={"api_version": "2024-10-21"},
        )
        emb = build_embeddings("azure", config, None)
        assert isinstance(emb, AzureOpenAIEmbeddings)
        assert emb.deployment == "embed-deployment"

    def test_ollama_embeddings(self):
        config = make_config(
            "ollama",
            api_key=None,
            default_embedding_model="nomic-embed-text",
            parameters={"host": "http://localhost:11434"},
        )
        emb = build_embeddings("ollama", config, None)
        assert isinstance(emb, OllamaEmbeddings)
        assert emb.model == "nomic-embed-text"

    def test_provider_without_embedding_model_raises(self):
        config = make_config("openai")  # no default_embedding_model
        with pytest.raises(ValueError, match="does not support embedding"):
            build_embeddings("openai", config, None)


class TestEmbeddingsAgentResolution:
    def test_agent_embedding_config_used(self):
        agent = make_agent_config("research_agent", "openai", "gpt-4o")
        agent.embedding_model = AgentModelConfig(
            model_id="text-embedding-3-large", provider="openai", parameters={}
        )
        cm = StubConfigManager(
            providers={
                "openai": make_config(
                    "openai", default_embedding_model="text-embedding-3-small"
                )
            },
            primary_provider="openai",
            agents={"research_agent": agent},
        )
        emb = LangChainModelFactory(cm).create_embeddings_for_agent("research_agent")
        assert isinstance(emb, OpenAIEmbeddings)
        assert emb.model == "text-embedding-3-large"

    def test_agent_without_embedding_config_uses_provider_default(self):
        cm = StubConfigManager(
            providers={
                "openai": make_config(
                    "openai", default_embedding_model="text-embedding-3-small"
                )
            },
            primary_provider="openai",
            agents={
                "research_agent": make_agent_config("research_agent", "openai", "gpt-4o")
            },
        )
        emb = LangChainModelFactory(cm).create_embeddings_for_agent("research_agent")
        assert emb.model == "text-embedding-3-small"

    def test_unavailable_embedding_provider_falls_back_to_primary(self):
        agent = make_agent_config("research_agent", "openai", "gpt-4o")
        agent.embedding_model = AgentModelConfig(
            model_id="gemini-embedding-001", provider="google", parameters={}
        )
        cm = StubConfigManager(
            providers={
                "openai": make_config(
                    "openai", default_embedding_model="text-embedding-3-small"
                ),
                "google": make_config(
                    "google", default_embedding_model="gemini-embedding-001"
                ),
            },
            primary_provider="openai",
            invalid_providers={"google"},
            agents={"research_agent": agent},
        )
        emb = LangChainModelFactory(cm).create_embeddings_for_agent("research_agent")
        assert isinstance(emb, OpenAIEmbeddings)
        assert emb.model == "text-embedding-3-small"

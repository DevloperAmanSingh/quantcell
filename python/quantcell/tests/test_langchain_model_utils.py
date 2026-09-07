"""Tests for LangChain model helpers in quantcell.utils.model (Phase 2)."""

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langchain_openai import AzureChatOpenAI, ChatOpenAI

from quantcell.utils.model import (
    chat_model_should_use_json_mode,
    describe_chat_model,
)


class TestChatModelShouldUseJsonMode:
    def test_google_uses_json_mode(self):
        model = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key="x")
        assert chat_model_should_use_json_mode(model) is True

    def test_plain_openai_uses_json_mode(self):
        # Mirrors the Agno helper: official OpenAI also prefers JSON mode here.
        model = ChatOpenAI(model="gpt-4o", api_key="x")
        assert chat_model_should_use_json_mode(model) is True

    def test_openai_compatible_base_url_uses_json_mode(self):
        model = ChatOpenAI(
            model="deepseek-chat", api_key="x", base_url="https://api.deepseek.com"
        )
        assert chat_model_should_use_json_mode(model) is True

    def test_azure_uses_json_mode(self):
        model = AzureChatOpenAI(
            azure_deployment="dep",
            api_key="x",
            azure_endpoint="https://r.openai.azure.com",
            api_version="2024-10-21",
        )
        assert chat_model_should_use_json_mode(model) is True

    def test_ollama_does_not_use_json_mode(self):
        model = ChatOllama(model="llama3.1")
        assert chat_model_should_use_json_mode(model) is False


class TestDescribeChatModel:
    def test_includes_model_and_class(self):
        model = ChatOpenAI(model="gpt-4o", api_key="x")
        description = describe_chat_model(model)
        assert "gpt-4o" in description
        assert "ChatOpenAI" in description

    def test_handles_google_model(self):
        model = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key="x")
        description = describe_chat_model(model)
        assert "gemini-2.5-flash" in description

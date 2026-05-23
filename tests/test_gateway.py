from __future__ import annotations

import pytest

from expediente.llm.gateway import (
    ModelProviderSettings,
    OpenAIModelGateway,
    UnconfiguredModelGateway,
    build_model_gateway_from_env,
    inspect_model_provider_env,
)


class FakeResponses:
    def __init__(self, output_text: str = "respuesta") -> None:
        self.output_text = output_text
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)

        class Response:
            output_text = self.output_text

        return Response()


class FakeClient:
    def __init__(self, responses: FakeResponses | None = None) -> None:
        self.responses = responses or FakeResponses()


def test_model_provider_settings_requires_api_key():
    settings = ModelProviderSettings(provider="openai", api_key="", model="gpt-4o")

    with pytest.raises(ValueError, match="API key"):
        settings.validate()


def test_unconfigured_gateway_marks_model_calls_out_of_scope():
    gateway = UnconfiguredModelGateway()

    with pytest.raises(NotImplementedError, match="foundation slice"):
        gateway.complete(system="system", user="hello")


def test_openai_gateway_calls_responses_api_with_model_and_prompts():
    responses = FakeResponses(" respuesta del modelo ")
    gateway = OpenAIModelGateway(
        ModelProviderSettings(provider="openai", api_key="key", model="gpt-test"),
        client=FakeClient(responses),
    )

    result = gateway.complete(system="sistema", user="usuario")

    assert result == "respuesta del modelo"
    assert responses.calls == [
        {
            "model": "gpt-test",
            "instructions": "sistema",
            "input": "usuario",
        }
    ]


def test_openai_gateway_rejects_empty_output_text():
    gateway = OpenAIModelGateway(
        ModelProviderSettings(provider="openai", api_key="key", model="gpt-test"),
        client=FakeClient(FakeResponses("")),
    )

    with pytest.raises(RuntimeError, match="output_text"):
        gateway.complete(system="sistema", user="usuario")


def test_build_model_gateway_from_env_returns_none_without_credentials(monkeypatch):
    monkeypatch.delenv("EXPEDIENTE_MODEL_API_KEY", raising=False)
    monkeypatch.delenv("EXPEDIENTE_MODEL_NAME", raising=False)

    assert build_model_gateway_from_env() is None


def test_inspect_model_provider_env_returns_safe_unconfigured_status(monkeypatch):
    monkeypatch.delenv("EXPEDIENTE_MODEL_API_KEY", raising=False)
    monkeypatch.delenv("EXPEDIENTE_MODEL_NAME", raising=False)

    status = inspect_model_provider_env()

    assert status.provider == "openai"
    assert status.model == ""
    assert status.configured is False
    assert status.api_key_present is False
    assert status.safe_label() == "Modelo: no configurado"


def test_inspect_model_provider_env_hides_api_key(monkeypatch):
    monkeypatch.setenv("EXPEDIENTE_MODEL_PROVIDER", "openai")
    monkeypatch.setenv("EXPEDIENTE_MODEL_API_KEY", "secret-key")
    monkeypatch.setenv("EXPEDIENTE_MODEL_NAME", "gpt-test")

    status = inspect_model_provider_env()

    assert status.configured is True
    assert status.api_key_present is True
    assert status.safe_label() == "Modelo: openai / gpt-test — API key configurada"
    assert "secret-key" not in status.safe_label()

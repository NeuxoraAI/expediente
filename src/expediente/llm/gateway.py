from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Protocol


class ModelGateway(Protocol):
    def complete(self, *, system: str, user: str) -> str:
        """Return a model completion for a future agent workflow."""


@dataclass(frozen=True)
class ModelProviderSettings:
    provider: str
    api_key: str
    model: str

    @classmethod
    def from_env(cls) -> "ModelProviderSettings":
        provider = os.environ.get("EXPEDIENTE_MODEL_PROVIDER", "openai").strip()
        api_key = os.environ.get("EXPEDIENTE_MODEL_API_KEY", "").strip()
        model = os.environ.get("EXPEDIENTE_MODEL_NAME", "").strip()
        settings = cls(provider=provider, api_key=api_key, model=model)
        settings.validate()
        return settings

    def validate(self) -> None:
        if not self.provider:
            raise ValueError("model provider is required")
        if not self.api_key:
            raise ValueError("model API key is required")
        if not self.model:
            raise ValueError("model name is required")


@dataclass(frozen=True)
class ModelProviderStatus:
    provider: str
    model: str
    configured: bool
    api_key_present: bool

    def safe_label(self) -> str:
        if not self.configured:
            return "Modelo: no configurado"
        return f"Modelo: {self.provider} / {self.model} — API key configurada"


def inspect_model_provider_env() -> ModelProviderStatus:
    provider = os.environ.get("EXPEDIENTE_MODEL_PROVIDER", "openai").strip() or "openai"
    api_key_present = bool(os.environ.get("EXPEDIENTE_MODEL_API_KEY", "").strip())
    model = os.environ.get("EXPEDIENTE_MODEL_NAME", "").strip()
    return ModelProviderStatus(
        provider=provider,
        model=model,
        configured=api_key_present and bool(model),
        api_key_present=api_key_present,
    )


@dataclass
class UnconfiguredModelGateway:
    settings: ModelProviderSettings | None = None

    def complete(self, *, system: str, user: str) -> str:
        raise NotImplementedError(
            "Model API calls are not implemented in this foundation slice; "
            "wire a provider adapter in the agent workflow slice."
        )


@dataclass
class OpenAIModelGateway:
    settings: ModelProviderSettings
    client: Any | None = None

    def __post_init__(self) -> None:
        self.settings.validate()
        if self.settings.provider.lower() != "openai":
            raise ValueError(f"unsupported model provider: {self.settings.provider}")
        if self.client is None:
            try:
                from openai import OpenAI
            except ModuleNotFoundError as exc:
                raise RuntimeError("OpenAI SDK is required. Install with `pip install -e .[llm]`.") from exc
            self.client = OpenAI(api_key=self.settings.api_key)

    def complete(self, *, system: str, user: str) -> str:
        response = self.client.responses.create(
            model=self.settings.model,
            instructions=system,
            input=user,
        )
        output_text = getattr(response, "output_text", "")
        if not output_text:
            raise RuntimeError("model response did not include output_text")
        return output_text.strip()


def build_model_gateway_from_env() -> ModelGateway | None:
    try:
        settings = ModelProviderSettings.from_env()
    except ValueError:
        return None
    if settings.provider.lower() == "openai":
        return OpenAIModelGateway(settings)
    raise ValueError(f"unsupported model provider: {settings.provider}")

"""Shared chat-model builder for synthesizers.

Builds a LangChain chat model from environment configuration, routed through a
LiteLLM-style OpenAI/Anthropic-compatible proxy.

Environment variables
----------------------
SYNTHESIZE_MODEL          Model name served by the proxy (e.g. ``claude-4.5-opus``).
SYNTHESIZE_PROXY_BASE_URL Base URL of the proxy (e.g. ``http://localhost:4000``).
SYNTHESIZE_LLM_API        Optional. Force the client surface:
                            ``anthropic`` -> native Messages API (ChatAnthropic),
                            ``openai``    -> OpenAI-compatible Chat Completions
                                             (ChatOpenAI, calls ``<base>/v1``).
                          When unset, defaults to ``anthropic`` for model names
                          starting with ``claude`` and ``openai`` otherwise.
SYNTHESIZE_TEMPERATURE    Optional sampling temperature (float).

Why the override exists
-----------------------
``deepagents`` unconditionally installs ``AnthropicPromptCachingMiddleware``,
which tags requests with Anthropic ``cache_control`` blocks whenever the model
is a ``ChatAnthropic`` instance. Some OpenAI-compatible proxies reject that
extra field. Setting ``SYNTHESIZE_LLM_API=openai`` routes ``claude-*`` models
through ``ChatOpenAI`` so the caching middleware is skipped and no
``cache_control`` is sent, while still hitting the same proxy and model.
"""

from __future__ import annotations

import os
from typing import Any


def resolve_llm_api(model_name: str) -> str:
    """Return the client surface to use: ``"anthropic"`` or ``"openai"``."""
    api = os.environ.get("SYNTHESIZE_LLM_API", "").strip().lower()
    if api in ("anthropic", "openai"):
        return api
    return "anthropic" if model_name.startswith("claude") else "openai"


def build_chat_model(temperature: float | None = None) -> Any:
    """Construct a LangChain chat model from environment configuration.

    Args:
        temperature: Sampling temperature. When ``None``, falls back to
            ``SYNTHESIZE_TEMPERATURE`` if set, else the model default.
    """
    model_name = os.environ["SYNTHESIZE_MODEL"]
    base_url = os.environ["SYNTHESIZE_PROXY_BASE_URL"]

    if temperature is None and "SYNTHESIZE_TEMPERATURE" in os.environ:
        temperature = float(os.environ["SYNTHESIZE_TEMPERATURE"])
    kwargs: dict[str, Any] = {} if temperature is None else {"temperature": temperature}

    if resolve_llm_api(model_name) == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=model_name,
            base_url=base_url,
            api_key="placeholder",  # proxy handles auth
            **kwargs,
        )

    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=model_name,
        base_url=base_url.rstrip("/") + "/v1",
        api_key="placeholder",  # proxy handles auth
        **kwargs,
    )

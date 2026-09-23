"""Thin helpers around the Anthropic SDK, shared by the generation scripts.

Conventions used throughout:
  * Claude Opus 5 with adaptive thinking (on by default for this model).
  * Streaming, because scripts and memory passes run long enough to risk an
    HTTP timeout on a non-streaming request.
  * `fallbacks: "default"` so a safety decline is retried server-side on
    Anthropic's recommended substitute rather than failing the workflow. The
    pinned SDK has no named parameter for it, so it goes through extra_body.
  * `output_config.format` for anything we parse, so the response is schema-valid
    JSON rather than prose we have to salvage.
"""
from __future__ import annotations

import json
from typing import Any, Iterable

import anthropic

MODEL = "claude-opus-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"


def _blocks(content: Iterable[Any]) -> str:
    return "".join(b.text for b in content if getattr(b, "type", None) == "text")


def _stream(
    client: anthropic.Anthropic,
    *,
    system: list[dict] | str,
    user: str | list[dict],
    max_tokens: int,
    effort: str,
    output_config_format: dict | None = None,
) -> Any:
    output_config: dict[str, Any] = {"effort": effort}
    if output_config_format:
        output_config["format"] = output_config_format
    with client.beta.messages.stream(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_config=output_config,
        betas=[FALLBACK_BETA],
        extra_body={"fallbacks": "default"},
    ) as stream:
        message = stream.get_final_message()
    if message.stop_reason == "refusal":
        details = getattr(message, "stop_details", None)
        raise RuntimeError(
            f"Claude declined the request (category={getattr(details, 'category', None)})"
        )
    if message.stop_reason == "max_tokens":
        raise RuntimeError(
            f"response hit max_tokens ({max_tokens}); raise it and retry"
        )
    log_usage(message)
    return message


def cached_system(prompt: str) -> list[dict]:
    """A system prompt marked for caching — it is identical across episodes."""
    return [{"type": "text", "text": prompt, "cache_control": {"type": "ephemeral"}}]


def text(
    client: anthropic.Anthropic,
    *,
    system: list[dict] | str,
    user: str | list[dict],
    max_tokens: int = 16000,
    effort: str = "high",
) -> str:
    message = _stream(
        client, system=system, user=user, max_tokens=max_tokens, effort=effort
    )
    return _blocks(message.content)


def structured(
    client: anthropic.Anthropic,
    *,
    system: list[dict] | str,
    user: str | list[dict],
    schema: dict,
    max_tokens: int = 32000,
    effort: str = "high",
) -> dict:
    message = _stream(
        client,
        system=system,
        user=user,
        max_tokens=max_tokens,
        effort=effort,
        output_config_format={"type": "json_schema", "schema": schema},
    )
    return json.loads(_blocks(message.content))


def log_usage(message: Any) -> None:
    """Print token usage so each workflow run shows what the episode cost."""
    usage = message.usage
    print(
        "  [claude] tokens in="
        f"{usage.input_tokens} cache_write={getattr(usage, 'cache_creation_input_tokens', 0)} "
        f"cache_read={getattr(usage, 'cache_read_input_tokens', 0)} "
        f"out={usage.output_tokens}"
    )

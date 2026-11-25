from typing import Any

import litellm


def extract_token_usage(
    response: Any,
    model: str,
    messages: list[dict[str, str]],
    reply_text: str,
) -> tuple[int, int]:
    """
    Extract per-request (input_tokens, output_tokens) from a LiteLLM response.

    Prefers exact provider-reported usage values; falls back to LiteLLM's
    token_counter only when usage fields are missing.
    """
    usage = getattr(response, "usage", None)
    prompt_tokens: int | None = None
    completion_tokens: int | None = None

    if usage is not None:
        if isinstance(usage, dict):
            prompt_tokens = usage.get("prompt_tokens")
            completion_tokens = usage.get("completion_tokens")
        else:
            prompt_tokens = getattr(usage, "prompt_tokens", None)
            completion_tokens = getattr(usage, "completion_tokens", None)

    if prompt_tokens is None:
        try:
            prompt_tokens = int(litellm.token_counter(model=model, messages=messages))
        except Exception:
            prompt_tokens = max(1, sum(len(m["content"].split()) for m in messages))

    if completion_tokens is None:
        try:
            completion_tokens = int(litellm.token_counter(model=model, text=reply_text))
        except Exception:
            completion_tokens = max(1, len(reply_text.split()))

    return int(prompt_tokens), int(completion_tokens)

"""Provider dispatch for the writing steps (resume tailoring, cover
letters, cold emails) - deliberately separate from jobradar's own scoring
LLM (see jobradar/llm.py, config `llm:` block) so a different provider or
model can be used for the content that actually reaches an employer, via
the `apply.tailor_llm` block in config.yaml.

groq/xkiro/openrouter/ollama all speak the OpenAI chat-completions shape,
so they reuse jobradar.llm.LLM directly - including its retry-with-backoff
and rate-limit-header pacing, already exercised by the scan pipeline.
Anthropic's API shape differs, so it gets its own small client here.
"""
from __future__ import annotations

import os
import time


def complete(cfg: dict, system: str | None, user_prompt: str, max_tokens: int) -> str:
    spec = cfg.get("apply", {}).get("tailor_llm", {})
    provider = spec.get("provider", "groq")
    model = spec.get("model", "openai/gpt-oss-120b")

    if provider == "anthropic":
        return _with_retries(lambda: _call_anthropic(model, system, user_prompt, max_tokens))
    # jobradar's own LLM client already retries and paces off the
    # provider's rate-limit headers - no need to duplicate that here.
    return _call_openai_compatible(provider, model, system, user_prompt, max_tokens)


def _with_retries(fn, attempts: int = 4, base_delay: float = 5.0):
    last_err = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            last_err = e
            status = getattr(e, "status_code", None)
            msg = str(e).lower()
            transient = status in (429, 500, 502, 503, 529) or "rate" in msg or "overloaded" in msg
            if not transient or i == attempts - 1:
                raise
            delay = base_delay * (2 ** i)
            print(f"  [apply-llm] transient error ({e}); retrying in {delay:.0f}s ({i + 1}/{attempts})...")
            time.sleep(delay)
    raise last_err


def _call_openai_compatible(provider: str, model: str, system: str | None,
                             user_prompt: str, max_tokens: int) -> str:
    from jobradar.llm import LLM
    client = LLM(provider, model)
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user_prompt})
    return client.chat(messages, max_tokens=max_tokens).strip()


def _call_anthropic(model: str, system: str | None, user_prompt: str, max_tokens: int) -> str:
    import anthropic

    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set (apply.tailor_llm.provider is 'anthropic')")
    client = anthropic.Anthropic(api_key=key)
    kwargs = dict(model=model, max_tokens=max_tokens,
                  messages=[{"role": "user", "content": user_prompt}])
    if system:
        kwargs["system"] = system
    msg = client.messages.create(**kwargs)
    return msg.content[0].text.strip()

"""공급자 선택. 실제 SDK는 고른 공급자만 불러온다 (gt만 쓸 때 키·패키지 불필요)."""
from .base import CallOptions, CallResult  # noqa: F401


def get_provider(name: str, opts: CallOptions):
    if name == "gt":
        from .gt import GTProvider
        return GTProvider(opts)
    if name == "anthropic":
        from .anthropic_provider import AnthropicProvider
        return AnthropicProvider(opts)
    if name == "openai":
        from .openai_provider import OpenAIProvider
        return OpenAIProvider(opts)
    if name == "openai_compat":
        from .openai_provider import OpenAICompatProvider
        return OpenAICompatProvider(opts)
    raise SystemExit(f"알 수 없는 공급자: {name}")

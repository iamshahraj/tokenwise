"""tokenwise — free, local MCP server for context window visibility."""

from tokenwise.tokenizer import (
    count_tokens,
    analyze_context,
    get_model_limits,
    warn_threshold,
)

__version__ = "0.1.0"
__all__ = ["count_tokens", "analyze_context", "get_model_limits", "warn_threshold"]

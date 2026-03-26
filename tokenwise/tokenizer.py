"""
tokenwise — core tokenizer engine
Supports: Anthropic, OpenAI, Google, Meta, Mistral, and fallback estimation.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import re


# ---------------------------------------------------------------------------
# Model registry — context window sizes (in tokens)
# ---------------------------------------------------------------------------

MODEL_LIMITS: dict[str, int] = {
    # Anthropic
    "claude-opus-4-5":              200_000,
    "claude-sonnet-4-5":            200_000,
    "claude-haiku-4-5":             200_000,
    "claude-3-5-sonnet-20241022":   200_000,
    "claude-3-5-haiku-20241022":    200_000,
    "claude-3-opus-20240229":       200_000,
    "claude-3-haiku-20240307":      200_000,

    # OpenAI
    "gpt-4o":                       128_000,
    "gpt-4o-mini":                  128_000,
    "gpt-4-turbo":                  128_000,
    "gpt-4":                          8_192,
    "gpt-3.5-turbo":                 16_385,
    "o1":                           200_000,
    "o1-mini":                      128_000,
    "o3":                           200_000,
    "o3-mini":                      200_000,

    # Google
    "gemini-2.0-flash":           1_000_000,
    "gemini-2.0-pro":             1_000_000,
    "gemini-1.5-pro":             1_000_000,
    "gemini-1.5-flash":           1_000_000,
    "gemini-1.0-pro":               32_000,

    # Meta (common local model names)
    "llama-3.3-70b":               128_000,
    "llama-3.2-90b":               128_000,
    "llama-3.2-11b":               128_000,
    "llama-3.1-405b":              128_000,
    "llama-3.1-70b":               128_000,
    "llama-3.1-8b":                128_000,
    "llama-3-70b":                   8_192,
    "llama-3-8b":                    8_192,

    # Mistral
    "mistral-large":               131_072,
    "mistral-medium":               32_000,
    "mistral-small":               131_072,
    "mistral-7b":                   32_000,
    "mixtral-8x7b":                 32_000,
    "mixtral-8x22b":                65_536,
}

# Friendly provider names for display
PROVIDER_MAP: dict[str, str] = {
    "claude":   "Anthropic",
    "gpt":      "OpenAI",
    "o1":       "OpenAI",
    "o3":       "OpenAI",
    "gemini":   "Google",
    "llama":    "Meta",
    "mistral":  "Mistral",
    "mixtral":  "Mistral",
}


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class TokenCount:
    model: str
    provider: str
    token_count: int
    limit: int
    usage_pct: float
    status: str          # "safe" | "warning" | "critical" | "over"
    bar: str             # visual progress bar string

@dataclass
class ContextBreakdown:
    model: str
    provider: str
    limit: int
    total_tokens: int
    usage_pct: float
    status: str
    bar: str
    system_tokens: int
    history_tokens: int
    files_tokens: int
    available_tokens: int
    breakdown_display: str

@dataclass
class ThresholdWarning:
    model: str
    total_tokens: int
    limit: int
    usage_pct: float
    triggered_thresholds: list[str]
    safe: bool
    message: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _detect_provider(model: str) -> str:
    model_lower = model.lower()
    for prefix, provider in PROVIDER_MAP.items():
        if model_lower.startswith(prefix):
            return provider
    return "Unknown"


def _get_limit(model: str) -> int:
    """Return token limit for model, with fuzzy fallback matching."""
    model_lower = model.lower()

    # Exact match first
    if model_lower in MODEL_LIMITS:
        return MODEL_LIMITS[model_lower]

    # Fuzzy: find the closest key that is a substring of the model name
    for key, limit in MODEL_LIMITS.items():
        if key in model_lower or model_lower in key:
            return limit

    # Default fallback — conservative 8k
    return 8_192


def _make_bar(pct: float, width: int = 20) -> str:
    filled = round(pct / 100 * width)
    empty = width - filled
    return "█" * filled + "░" * empty


def _status(pct: float) -> str:
    if pct >= 100:
        return "over"
    if pct >= 95:
        return "critical"
    if pct >= 70:
        return "warning"
    return "safe"


def _count_tokens_for_text(text: str, model: str) -> int:
    """
    Count tokens for raw text using the best available library for the model.
    Falls back gracefully if a library is not installed.
    """
    model_lower = model.lower()

    # --- OpenAI models: use tiktoken ---
    if any(model_lower.startswith(p) for p in ("gpt", "o1", "o3")):
        try:
            import tiktoken
            try:
                enc = tiktoken.encoding_for_model(model_lower)
            except KeyError:
                enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))
        except ImportError:
            pass  # fall through to char estimation

    # --- Anthropic models: use anthropic SDK ---
    if model_lower.startswith("claude"):
        try:
            import anthropic
            client = anthropic.Anthropic()
            response = client.messages.count_tokens(
                model=model,
                messages=[{"role": "user", "content": text}],
            )
            return response.input_tokens
        except Exception:
            pass  # fall through to char estimation

    # --- Google models: use google-generativeai ---
    if model_lower.startswith("gemini"):
        try:
            import google.generativeai as genai
            m = genai.GenerativeModel(model)
            result = m.count_tokens(text)
            return result.total_tokens
        except Exception:
            pass

    # --- HuggingFace transformers (Llama, Mistral, etc.) ---
    if any(model_lower.startswith(p) for p in ("llama", "mistral", "mixtral")):
        try:
            from transformers import AutoTokenizer
            # Map common shorthand names to HF repo IDs
            hf_map = {
                "llama-3.1-8b":  "meta-llama/Meta-Llama-3.1-8B",
                "mistral-7b":    "mistralai/Mistral-7B-v0.1",
                "mixtral-8x7b":  "mistralai/Mixtral-8x7B-v0.1",
            }
            repo = hf_map.get(model_lower, model)
            tokenizer = AutoTokenizer.from_pretrained(repo)
            return len(tokenizer.encode(text))
        except Exception:
            pass

    # --- Universal fallback: character-based estimation ---
    # Empirically ~4 chars per token across most modern tokenizers
    return max(1, len(text) // 4)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def count_tokens(text: str, model: str) -> TokenCount:
    """Count tokens in text for the given model."""
    token_count = _count_tokens_for_text(text, model)
    limit       = _get_limit(model)
    pct         = round(token_count / limit * 100, 1)
    provider    = _detect_provider(model)

    return TokenCount(
        model        = model,
        provider     = provider,
        token_count  = token_count,
        limit        = limit,
        usage_pct    = pct,
        status       = _status(pct),
        bar          = _make_bar(pct),
    )


def analyze_context(
    system: str = "",
    history: list[dict] | None = None,
    files: str = "",
    model: str = "claude-sonnet-4-5",
) -> ContextBreakdown:
    """
    Break down token usage by component.

    Args:
        system:  System prompt text
        history: List of message dicts [{"role": ..., "content": ...}]
        files:   All file content concatenated
        model:   Model name to count against
    """
    history = history or []

    system_tokens  = _count_tokens_for_text(system, model) if system else 0
    history_text   = " ".join(m.get("content", "") for m in history)
    history_tokens = _count_tokens_for_text(history_text, model) if history_text else 0
    files_tokens   = _count_tokens_for_text(files, model) if files else 0

    total     = system_tokens + history_tokens + files_tokens
    limit     = _get_limit(model)
    pct       = round(total / limit * 100, 1)
    provider  = _detect_provider(model)
    available = max(0, limit - total)

    bar = _make_bar(pct)

    breakdown = (
        f"Context Usage [{model}]\n"
        f"{bar} {pct}% ({total:,} / {limit:,} tokens)\n\n"
        f"├── System prompt:     {system_tokens:>8,} tokens\n"
        f"├── Conversation:      {history_tokens:>8,} tokens\n"
        f"├── Files in context:  {files_tokens:>8,} tokens\n"
        f"└── Available:         {available:>8,} tokens"
    )

    return ContextBreakdown(
        model             = model,
        provider          = provider,
        limit             = limit,
        total_tokens      = total,
        usage_pct         = pct,
        status            = _status(pct),
        bar               = bar,
        system_tokens     = system_tokens,
        history_tokens    = history_tokens,
        files_tokens      = files_tokens,
        available_tokens  = available,
        breakdown_display = breakdown,
    )


def get_model_limits(model: Optional[str] = None) -> dict:
    """
    Return context window limit for one model, or the full registry.

    Args:
        model: Model name (optional). If None, returns full registry.
    """
    if model:
        limit    = _get_limit(model)
        provider = _detect_provider(model)
        return {
            "model":    model,
            "provider": provider,
            "limit":    limit,
            "limit_k":  f"{limit // 1000}k",
        }

    # Return grouped registry
    grouped: dict[str, list[dict]] = {}
    for m, limit in MODEL_LIMITS.items():
        provider = _detect_provider(m)
        grouped.setdefault(provider, []).append({
            "model":   m,
            "limit":   limit,
            "limit_k": f"{limit // 1000}k",
        })
    return grouped


def warn_threshold(
    text: str = "",
    system: str = "",
    history: list[dict] | None = None,
    files: str = "",
    model: str = "claude-sonnet-4-5",
    thresholds: list[int] | None = None,
) -> ThresholdWarning:
    """
    Check if token usage has crossed warning thresholds.

    Args:
        text:       Raw text to count (alternative to system/history/files)
        system:     System prompt
        history:    Conversation history
        files:      File content
        model:      Model name
        thresholds: List of % thresholds to check (default: [70, 85, 95])
    """
    thresholds = thresholds or [70, 85, 95]
    history    = history or []

    if text:
        total = _count_tokens_for_text(text, model)
    else:
        system_t  = _count_tokens_for_text(system, model) if system else 0
        hist_text = " ".join(m.get("content", "") for m in history)
        hist_t    = _count_tokens_for_text(hist_text, model) if hist_text else 0
        files_t   = _count_tokens_for_text(files, model) if files else 0
        total     = system_t + hist_t + files_t

    limit    = _get_limit(model)
    pct      = round(total / limit * 100, 1)
    triggered = [f"{t}%" for t in sorted(thresholds) if pct >= t]
    safe     = len(triggered) == 0

    if pct >= 100:
        message = f"⛔ Over limit! {total:,} / {limit:,} tokens ({pct}%). Responses may be truncated."
    elif triggered:
        worst = triggered[-1]
        message = f"⚠️  {worst} threshold crossed — {total:,} / {limit:,} tokens used ({pct}%). Consider trimming context."
    else:
        next_t = next((t for t in sorted(thresholds) if pct < t), None)
        remaining = limit - total
        message = f"✅ Context healthy — {pct}% used ({total:,} / {limit:,} tokens). {remaining:,} tokens remaining."

    return ThresholdWarning(
        model                = model,
        total_tokens         = total,
        limit                = limit,
        usage_pct            = pct,
        triggered_thresholds = triggered,
        safe                 = safe,
        message              = message,
    )

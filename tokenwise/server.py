"""
tokenwise — MCP server
Exposes token counting and context analysis tools to any MCP-compatible IDE.
"""

from __future__ import annotations
import asyncio
import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

from tokenwise.tokenizer import (
    count_tokens,
    analyze_context,
    get_model_limits,
    warn_threshold,
)

# ---------------------------------------------------------------------------
# Server init
# ---------------------------------------------------------------------------

app = Server("tokenwise")


# ---------------------------------------------------------------------------
# Tool definitions — what the IDE sees
# ---------------------------------------------------------------------------

@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="count_tokens",
            description=(
                "Count the number of tokens in a given text for a specific model. "
                "Use this to check how large a piece of text is before sending it."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text to count tokens for.",
                    },
                    "model": {
                        "type": "string",
                        "description": (
                            "Model name to count tokens against. "
                            "Examples: claude-sonnet-4-5, gpt-4o, gemini-1.5-pro, llama-3.1-8b. "
                            "Defaults to claude-sonnet-4-5."
                        ),
                        "default": "claude-sonnet-4-5",
                    },
                },
                "required": ["text"],
            },
        ),

        types.Tool(
            name="analyze_context",
            description=(
                "Break down the current context window usage by component — "
                "system prompt, conversation history, and files. "
                "Shows a visual bar of how full the context window is."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "model": {
                        "type": "string",
                        "description": "Model name. Defaults to claude-sonnet-4-5.",
                        "default": "claude-sonnet-4-5",
                    },
                    "system": {
                        "type": "string",
                        "description": "The system prompt text (if any).",
                        "default": "",
                    },
                    "history": {
                        "type": "array",
                        "description": (
                            "Conversation history as a list of message objects "
                            "with 'role' and 'content' fields."
                        ),
                        "items": {
                            "type": "object",
                            "properties": {
                                "role":    {"type": "string"},
                                "content": {"type": "string"},
                            },
                        },
                        "default": [],
                    },
                    "files": {
                        "type": "string",
                        "description": "All file content currently in context, concatenated.",
                        "default": "",
                    },
                },
                "required": ["model"],
            },
        ),

        types.Tool(
            name="get_model_limits",
            description=(
                "Get the context window size (in tokens) for any supported model. "
                "Call without arguments to see all supported models and their limits."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "model": {
                        "type": "string",
                        "description": (
                            "Model name to look up. "
                            "Leave empty to get the full model registry."
                        ),
                        "default": "",
                    },
                },
                "required": [],
            },
        ),

        types.Tool(
            name="warn_threshold",
            description=(
                "Check whether the current context usage has crossed warning thresholds "
                "(70%, 85%, 95%). Returns a clear status message and which thresholds "
                "have been triggered. Use this proactively to avoid hitting the context limit."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "model": {
                        "type": "string",
                        "description": "Model name. Defaults to claude-sonnet-4-5.",
                        "default": "claude-sonnet-4-5",
                    },
                    "text": {
                        "type": "string",
                        "description": "Raw text to check (use instead of system/history/files for quick checks).",
                        "default": "",
                    },
                    "system": {
                        "type": "string",
                        "description": "System prompt text.",
                        "default": "",
                    },
                    "history": {
                        "type": "array",
                        "description": "Conversation history as message objects.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "role":    {"type": "string"},
                                "content": {"type": "string"},
                            },
                        },
                        "default": [],
                    },
                    "files": {
                        "type": "string",
                        "description": "File content in context.",
                        "default": "",
                    },
                    "thresholds": {
                        "type": "array",
                        "description": "Custom warning thresholds as percentages. Defaults to [70, 85, 95].",
                        "items": {"type": "integer"},
                        "default": [70, 85, 95],
                    },
                },
                "required": [],
            },
        ),
    ]


# ---------------------------------------------------------------------------
# Tool handlers — what runs when the IDE calls a tool
# ---------------------------------------------------------------------------

@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:

    try:
        if name == "count_tokens":
            result = count_tokens(
                text  = arguments["text"],
                model = arguments.get("model", "claude-sonnet-4-5"),
            )
            output = (
                f"Token count for [{result.model}]\n"
                f"{result.bar} {result.usage_pct}%\n\n"
                f"  Tokens:   {result.token_count:,}\n"
                f"  Limit:    {result.limit:,}\n"
                f"  Provider: {result.provider}\n"
                f"  Status:   {result.status.upper()}"
            )

        elif name == "analyze_context":
            result = analyze_context(
                system  = arguments.get("system", ""),
                history = arguments.get("history", []),
                files   = arguments.get("files", ""),
                model   = arguments.get("model", "claude-sonnet-4-5"),
            )
            output = result.breakdown_display

        elif name == "get_model_limits":
            model  = arguments.get("model", "").strip()
            result = get_model_limits(model if model else None)

            if isinstance(result, dict) and "limit" in result:
                # Single model lookup
                output = (
                    f"Model:    {result['model']}\n"
                    f"Provider: {result['provider']}\n"
                    f"Limit:    {result['limit']:,} tokens ({result['limit_k']})"
                )
            else:
                # Full registry — grouped by provider
                lines = ["Supported models and context window limits:\n"]
                for provider, models in sorted(result.items()):
                    lines.append(f"{provider}")
                    for m in models:
                        lines.append(f"  {m['model']:<40} {m['limit_k']:>6}")
                    lines.append("")
                output = "\n".join(lines)

        elif name == "warn_threshold":
            result = warn_threshold(
                text       = arguments.get("text", ""),
                system     = arguments.get("system", ""),
                history    = arguments.get("history", []),
                files      = arguments.get("files", ""),
                model      = arguments.get("model", "claude-sonnet-4-5"),
                thresholds = arguments.get("thresholds", [70, 85, 95]),
            )
            output = (
                f"{result.message}\n\n"
                f"  Model:      {result.model}\n"
                f"  Tokens:     {result.total_tokens:,} / {result.limit:,}\n"
                f"  Usage:      {result.usage_pct}%\n"
                f"  Triggered:  {', '.join(result.triggered_thresholds) or 'none'}"
            )

        else:
            output = f"Unknown tool: {name}"

    except Exception as e:
        output = f"tokenwise error in '{name}': {str(e)}"

    return [types.TextContent(type="text", text=output)]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


def run() -> None:
    """CLI entry point — called by `python -m tokenwise` or the `tokenwise` command."""
    asyncio.run(main())


if __name__ == "__main__":
    run()

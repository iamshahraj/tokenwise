# tokenwise 🪙

> You're already paying for tokens. At least stop wasting them.

**tokenwise** is a free, local MCP server that gives your AI-powered IDE full visibility into context window usage — before you hit the wall and your AI gets dumb.

Works with **Cursor**, **Claude Code**, **Windsurf**, **Cline**, **Continue**, and any MCP-compatible client.

---

## The Problem

You're coding with AI. Things are going great. Then suddenly — the responses get vague, it forgets what you told it 10 messages ago, and you have no idea why.

You just silently hit your context window limit.

You had no warning. No visibility. No control.

**tokenwise fixes that.**

---

## What It Does

tokenwise runs as a local MCP server on your machine. No data leaves your computer. No API key needed. No cost.

It exposes tools your IDE can call to understand exactly what's happening with your context:

| Tool | What it does |
|------|-------------|
| `count_tokens` | Count tokens for any text, for any model |
| `analyze_context` | Break down token usage by system prompt, history, and files |
| `get_model_limits` | Get the context window size for any supported model |
| `warn_threshold` | Get alerted at 70%, 85%, and 95% usage |

### Example output from `analyze_context`

```text
Context Usage [claude-sonnet-4-5]
████████████░░░░░░░░ 62% (124,000 / 200,000 tokens)
├── System Prompt:  8,200
├── IDE Hidden Rules: 4,100
├── Conversation:   68,300
├── Files:          43,400
└── Available:      76,000
```

*Note: `tokenwise` also automatically checks your folder for things like `.cursorrules` or `.clinerules` so their hidden token usage is correctly included in the total. It just counts the tokens locally—nothing is ever stored or sent out.*

### Example output from `warn_threshold`

```text
⚠️  95% threshold crossed — 192,400 / 200,000 tokens used (96.2%). Consider trimming context.

  Model:      claude-sonnet-4-5
  Tokens:     192,400 / 200,000
  Usage:      96.2%
  Triggered:  70%, 85%, 95%
```

### Example output from `get_model_limits`

If you ever forget what the maximum limit is for the specific model you're chatting with, just ask your AI *"what is the limit for gemini-2.0-pro?"* and it will check its internal registry:

```text
Model:    gemini-2.0-pro
Provider: Google
Limit:    1,000,000 tokens (1000k)
```

---

## Supported Models

| Provider | Models |
|----------|--------|
| **Anthropic** | Claude 3.5 Sonnet, Claude 3 Opus, Claude 3 Haiku, Claude 4 series |
| **OpenAI** | GPT-4o, GPT-4 Turbo, GPT-3.5 Turbo, o1, o3 |
| **Google** | Gemini 1.5 Pro, Gemini 1.5 Flash, Gemini 2.0 |
| **Meta** | Llama 3, Llama 3.1, Llama 3.2 |
| **Mistral** | Mistral 7B, Mixtral 8x7B, Mistral Large |
| **Fallback** | Any unknown model (character-based estimation) |

---

## Installation

### Requirements
- Python 3.10+
- Any MCP-compatible IDE (Cursor, Claude Code, Windsurf, etc.)

### Install from PyPI

```bash
pip install mcp-tokenwise
```

### Configure in your IDE

**Cursor / Windsurf** — add to your MCP config (`~/.cursor/mcp.json` or equivalent):

```json
{
  "mcpServers": {
    "tokenwise": {
      "command": "python",
      "args": ["-m", "tokenwise"]
    }
  }
}
```

**Claude Code:**

```bash
claude mcp add tokenwise python -m tokenwise
```

That's it. Restart your IDE and tokenwise is live.

---

## Usage Examples

Once connected, you can ask your AI assistant directly:

```
"How many tokens am I using right now?"
"Am I close to my context limit?"
"Break down what's eating my context window"
"What's the token limit for GPT-4o?"
```

tokenwise handles it automatically in the background.

---

## Roadmap

### Phase 1 — Visibility (current)
- [x] Token counting for all major models
- [x] Context breakdown by component
- [x] Model limit registry
- [x] Threshold warnings (70 / 85 / 95%)

### Phase 2 — Active Management (coming soon)
- [ ] `trim_context` — intelligently remove least relevant parts
- [ ] `compress_history` — summarize old turns to free space
- [ ] `prioritize_files` — rank files by relevance to current task
- [ ] `suggest_split` — detect when a task should be broken up

---

## Why Local-Only?

Your code is private. Your conversations are private. tokenwise never phones home — it runs entirely on your machine, reads nothing, stores nothing.

If you're already paying $20–200/month on AI tools, the last thing you need is another service with access to your codebase.

---

## Contributing

tokenwise is early and we'd love contributions:

- Add tokenizer support for a new model family
- Improve estimation accuracy for edge cases
- Test with a new MCP client and report back
- Suggest a Phase 2 feature

Open an issue or PR — all welcome.

---

## License

MIT — free forever.

---

*Built because every developer deserves to know where their tokens are going.*

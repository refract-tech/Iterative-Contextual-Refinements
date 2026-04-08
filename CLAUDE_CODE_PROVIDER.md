# Claude Code Provider for Iterative Studio

Use your **Claude Code plan credits** as the AI backend for Iterative Studio — zero API costs, full agentic isolation per call.

## How It Works

```
Iterative Studio (React) → ClaudeCodeProvider.ts → .claude_ipc/request.json
                                                          ↓
bridge_claude_code.py ← polls → reads request → calls `claude` CLI
                                                          ↓
                                     .claude_ipc/response.json → Iterative Studio
```

Each AI call is routed through the `claude` CLI as an isolated subagent. The subagent has no shared context with other calls — exactly like calling a separate API instance. This provides true agentic isolation for the Deepthink pipeline.

## Setup

### Prerequisites

- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) installed and authenticated
- Node.js 18+
- Python 3.10+

### Installation

```bash
# Clone the fork
git clone https://github.com/refract-tech/Iterative-Contextual-Refinements.git
cd Iterative-Contextual-Refinements

# Install dependencies
npm install --legacy-peer-deps
```

### Running

You need **two terminals**:

**Terminal 1 — Bridge (Python)**
```bash
python bridge_claude_code.py
```

**Terminal 2 — Frontend (React)**
```bash
npm run dev
```

### Configuration

1. Open the app in your browser (usually `http://localhost:5173`)
2. Go to Settings → Providers
3. Click "Claude Code (Plan Credits)"
4. Enter any string as API key (it's not used, but required by the UI)
5. Select `claude-code-opus` as your model

### Model Selection

| Model ID | Claude Model | Use Case |
|----------|-------------|----------|
| `claude-code-opus` | Opus 4.6 | Best quality, strategy/critique/judge |
| `claude-code-sonnet` | Sonnet 4.6 | Good balance, execution agents |
| `claude-code-haiku` | Haiku 4.5 | Fast, hypothesis testing |

You can assign different models to different Deepthink agents via the per-agent model selection in the UI.

## Cost

**Zero API costs.** All calls use your Claude Code plan credits (Pro/Max subscription). The bridge calls `claude --print` which uses plan allocation, not metered API.

## Limitations

- Requires Claude Code CLI installed locally
- Sequential processing (one request at a time via the bridge)
- ~10-60 second latency per call (CLI startup + inference)
- No streaming (response delivered complete)
- No image/vision support (text-only prompts)

## Architecture

### Files Added/Modified

| File | Change |
|------|--------|
| `Routing/ClaudeCodeProvider.ts` | **NEW** — AI provider using file-based IPC |
| `Routing/AIProvider.ts` | Added `claude-code` to provider factory |
| `Routing/ProviderManager.ts` | Added `claude-code` provider config + models |
| `bridge_claude_code.py` | **NEW** — Python bridge polling for requests |

### IPC Protocol

Request (`.claude_ipc/request.json`):
```json
{
  "id": "req_1712537000_abc123",
  "system_prompt": "You are a Master Strategy Agent...",
  "user_prompt": "Core Challenge: ...",
  "temperature": 0.7,
  "model": "claude-code-opus",
  "json_output": false,
  "timestamp": "2026-04-08T01:30:00.000Z"
}
```

Response (`.claude_ipc/response.json`):
```json
{
  "id": "req_1712537000_abc123",
  "content": "The full response text...",
  "timestamp": "2026-04-08T01:30:45"
}
```

Lock file (`.claude_ipc/request.lock`): Contains the request ID. Presence signals the bridge that a request is ready.

## License

Apache-2.0 (same as upstream Iterative Studio)

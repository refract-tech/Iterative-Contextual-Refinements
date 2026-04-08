# Claude Code Provider for Iterative Studio

Use your **Claude Code plan credits** as the AI backend for Iterative Studio — zero API costs, full agentic isolation per call.

## How It Works

```
Iterative Studio (React UI)
        │
        ▼
ClaudeCodeProvider.ts  ──HTTP POST──►  bridge_claude_code.py (localhost:4141)
                                              │
                                              ▼
                                        claude CLI (--print --model opus -p -)
                                              │
                                              ▼
                                        HTTP Response  ──►  Iterative Studio
```

Each AI call is routed through the `claude` CLI as an isolated process. Every call starts fresh with no shared context — exactly like calling a separate API instance. This provides true agentic isolation for the Deepthink pipeline.

## Quick Start

### Prerequisites

- **Claude Code CLI** installed and authenticated (`claude --version` should work)
- **Node.js 18+**
- **Python 3.10+**
- A Claude **Pro or Max** subscription (plan credits)

### Step 1: Clone and Install

```bash
git clone https://github.com/refract-tech/Iterative-Contextual-Refinements.git
cd Iterative-Contextual-Refinements
npm install --legacy-peer-deps
```

### Step 2: Start the Bridge (Terminal 1)

```bash
python bridge_claude_code.py
```

You should see:
```
============================================================
  Claude Code Bridge for Iterative Studio
  http://localhost:4141
  Claude binary: C:\Users\...\claude.exe
============================================================
  Waiting for requests...
```

If the bridge says `Claude binary: claude` (not a full path), the CLI is not in your PATH. The bridge auto-detects the binary on Windows from `AppData/Roaming/Claude/claude-code/`. On Mac/Linux, ensure `claude` is in your PATH.

### Step 3: Start the Frontend (Terminal 2)

```bash
npm run dev
```

Opens at `http://localhost:5173` (or next available port).

### Step 4: Configure the Provider

1. Open the app in your browser
2. Click the **Settings/Provider** panel (sidebar)
3. Find **"Claude Code (Plan Credits)"**
4. Enter any string as API key (e.g., `not-needed`) — it's required by the UI but not used
5. Click **"Configure Provider"**
6. The provider should show as **CONFIGURED** with available models

### Step 5: Select Model and Run

1. On the main screen, select **`claude-code-opus`** from the model dropdown
2. Set Temperature: **0.7**, Top P: **0.9** (recommended for Deepthink)
3. Select **Deepthink** mode
4. Enter your challenge/problem
5. Click **Generate**

The bridge terminal will show each request being processed:
```
[1] req_xxx | model=claude-code-opus | sys=48390c | usr=1833c
  Done in 39.0s (3369 chars)
```

## Available Models

| Model ID | Claude Model | Speed | Best For |
|----------|-------------|-------|----------|
| `claude-code-opus` | Claude Opus 4.6 | ~30-90s/call | Strategy, Critique, Final Judge |
| `claude-code-sonnet` | Claude Sonnet 4.6 | ~10-30s/call | Execution, Sub-strategies |
| `claude-code-haiku` | Claude Haiku 4.5 | ~5-15s/call | Testing, quick iterations |

You can assign different models to different Deepthink agents in the Settings panel under "Per-Agent Model Selection."

## Supported Modes

| Mode | Status | Notes |
|------|--------|-------|
| **Deepthink** | ✅ Fully supported | Complete pipeline including Iterative Corrections + Solution Pool |
| **Contextual** | ✅ Should work | Uses same `callAI()` path |
| **Refine** | ✅ Should work | Uses same `callAI()` path |
| **Adaptive Deepthink** | ❌ Not supported | Requires LangChain tool-calling integration not available via CLI bridge |
| **Agentic** | ❌ Not supported | Same limitation as Adaptive Deepthink |

## Exporting Results

After a run completes:
1. Open the **sidebar** (left panel)
2. Click **"Export Config"** button (bottom of sidebar)
3. Downloads a `.msgpack.gz` file with the complete pipeline state

To import a previous run:
1. Click **"Import Config"** next to the export button
2. Select the `.msgpack.gz` file

## Cost

**Zero API costs.** All calls use your Claude Code plan credits (Pro/Max subscription). The bridge calls `claude --print` which uses plan allocation, not metered API.

## Performance

Typical timing per Deepthink step:
- **Opus**: 30-90 seconds (longer for complex prompts with 40K+ system prompts)
- **Haiku**: 5-15 seconds
- **Full Deepthink run (Opus, 3 strategies, 2 sub, 3 hypotheses, no iterations)**: ~20-30 minutes
- **Full with 3 iterations**: ~45-90 minutes

The bridge processes requests **sequentially** — one at a time. The Iterative Studio frontend queues requests and waits.

## Troubleshooting

### "Failed to configure provider"
- Make sure you restarted `npm run dev` after the code changes
- Enter any string in the API key field (the field is required but the value is ignored)

### Bridge shows "Done in 0.0s (69 chars)"
- The claude CLI is not being found. Check that `bridge_claude_code.py` shows the correct binary path at startup
- Test manually: `claude --print --model haiku -p "hello"`

### "JSON5: invalid character" in the browser
- Claude sometimes wraps JSON in markdown code fences (` ```json ... ``` `). The bridge strips these automatically. If you still see this, restart the bridge to pick up the latest code.

### ConnectionAbortedError in bridge terminal
- Normal when a request takes >2 minutes. The frontend times out the HTTP connection, but the bridge catches this gracefully and continues processing. The response is still used on the next retry.

### Unicode/encoding errors
- The bridge forces UTF-8 encoding. If you see encoding errors, make sure you're running the latest version of `bridge_claude_code.py`.

### Adaptive Deepthink says "Unsupported tool-calling provider"
- This mode requires LangChain tool-calling integration which is not available through the CLI bridge. Use standard **Deepthink** mode instead.

## Architecture

### Files Added/Modified

| File | Change | Description |
|------|--------|-------------|
| `Routing/ClaudeCodeProvider.ts` | **NEW** | HTTP-based AI provider for Claude Code |
| `Routing/AIProvider.ts` | Modified | Added `claude-code` to provider factory + import |
| `Routing/ProviderManager.ts` | Modified | Registered provider config + model list |
| `bridge_claude_code.py` | **NEW** | Python HTTP server bridging requests to claude CLI |
| `.gitignore` | Modified | Added `.claude_ipc/` directory |

### Bridge Protocol

The bridge runs an HTTP server on `localhost:4141`.

**POST /generate**
```json
{
  "id": "req_1712537000_abc123",
  "system_prompt": "You are a Master Strategy Agent...",
  "user_prompt": "Core Challenge: ...",
  "temperature": 0.7,
  "model": "claude-code-opus",
  "json_output": false
}
```

Response:
```json
{
  "id": "req_1712537000_abc123",
  "content": "The full response text...",
  "elapsed_seconds": 45.2
}
```

**POST /health** — Returns `{"status": "ok", "requests": N}`

### How the Bridge Calls Claude

```bash
claude --print --model opus -p -
```

- `--print`: Output-only mode (no interactive UI)
- `--model opus`: Select the model
- `-p -`: Read prompt from stdin (avoids Windows command-line length limits)

The prompt is passed via stdin as: `{system_prompt}\n\n---\n\n{user_prompt}`

## Contributing

This is a fork of [Iterative Studio](https://github.com/ryoiki-tokuiten/Iterative-Contextual-Refinements) by ryoiki-tokuiten. The Claude Code provider is an independent addition that does not modify any core pipeline logic.

To add support for other CLI-based AI tools, create a new provider following the `ClaudeCodeProvider.ts` pattern and add a corresponding case in the bridge.

## License

Apache-2.0 (same as upstream)

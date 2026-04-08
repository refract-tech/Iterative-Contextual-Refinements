#!/usr/bin/env python3
"""Bridge between Iterative Studio and Claude Code.

Polls for request files written by ClaudeCodeProvider.ts,
processes them via Claude Code CLI subagents, and writes responses.

Usage:
    # In one terminal, start the bridge:
    python bridge_claude_code.py

    # In another terminal, start the frontend:
    npm run dev

    # In the UI, select "Claude Code (Plan Credits)" as provider
    # and "claude-code-opus" as the model.

The bridge runs in the same directory as the Iterative Studio project.
It uses Claude Code's `claude` CLI to process each request as an
isolated subagent call — full agentic isolation, plan credits only.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

# IPC directory — must match ClaudeCodeProvider.ts
IPC_DIR = Path(__file__).parent / ".claude_ipc"
REQUEST_FILE = IPC_DIR / "request.json"
RESPONSE_FILE = IPC_DIR / "response.json"
LOCK_FILE = IPC_DIR / "request.lock"

POLL_INTERVAL = 0.5  # seconds


def ensure_ipc_dir():
    IPC_DIR.mkdir(exist_ok=True)


def call_claude_code(system_prompt: str, user_prompt: str, model: str = "opus") -> str:
    """Call Claude Code CLI as a subagent and return the response text."""
    # Map model names to Claude Code model flags
    model_map = {
        "claude-code-opus": "opus",
        "claude-code-sonnet": "sonnet",
        "claude-code-haiku": "haiku",
        "opus": "opus",
        "sonnet": "sonnet",
        "haiku": "haiku",
    }
    claude_model = model_map.get(model, "opus")

    # Build the full prompt
    full_prompt = ""
    if system_prompt:
        full_prompt += f"{system_prompt}\n\n---\n\n"
    full_prompt += user_prompt

    # Call claude CLI
    # --print: output only the response (no interactive UI)
    # --model: select the model
    # --no-input: don't wait for user input (non-interactive)
    try:
        result = subprocess.run(
            ["claude", "--print", "--model", claude_model, "--no-input", "-p", full_prompt],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
            cwd=str(Path(__file__).parent),
        )
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            error_msg = result.stderr.strip() or f"Claude Code exited with code {result.returncode}"
            print(f"  ERROR: {error_msg}", file=sys.stderr)
            return f"[ERROR] Claude Code failed: {error_msg}"
    except subprocess.TimeoutExpired:
        return "[ERROR] Claude Code timed out after 300 seconds"
    except FileNotFoundError:
        return "[ERROR] 'claude' CLI not found. Is Claude Code installed and in PATH?"
    except Exception as e:
        return f"[ERROR] Unexpected error: {e}"


def process_request(request: dict) -> dict:
    """Process a single request and return the response."""
    req_id = request.get("id", "unknown")
    system_prompt = request.get("system_prompt", "")
    user_prompt = request.get("user_prompt", "")
    model = request.get("model", "claude-code-opus")

    # Handle conversation history if present
    history = request.get("conversation_history")
    if history:
        # Build a combined prompt from conversation history
        parts = []
        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_prompt = f"{system_prompt}\n\n{content}" if system_prompt else content
            elif role == "assistant":
                parts.append(f"[Previous Response]\n{content}")
            elif role == "user":
                parts.append(f"[User]\n{content}")
        if parts:
            user_prompt = "\n\n".join(parts)
            if not user_prompt.strip():
                user_prompt = history[-1].get("content", "")

    print(f"  System prompt: {len(system_prompt)} chars")
    print(f"  User prompt: {len(user_prompt)} chars")
    print(f"  Model: {model}")

    content = call_claude_code(system_prompt, user_prompt, model)

    return {
        "id": req_id,
        "content": content,
        "text": content,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def main():
    print("=" * 60)
    print("  Claude Code Bridge for Iterative Studio")
    print("=" * 60)
    print(f"  IPC directory: {IPC_DIR}")
    print(f"  Polling every {POLL_INTERVAL}s")
    print(f"  Waiting for requests...")
    print()

    ensure_ipc_dir()

    # Clean up stale files
    for f in [REQUEST_FILE, RESPONSE_FILE, LOCK_FILE]:
        if f.exists():
            f.unlink()

    request_count = 0

    while True:
        try:
            if LOCK_FILE.exists():
                # A request is ready
                lock_content = LOCK_FILE.read_text().strip()

                if REQUEST_FILE.exists():
                    request_count += 1
                    request_raw = REQUEST_FILE.read_text(encoding="utf-8")
                    request = json.loads(request_raw)

                    print(f"[{request_count}] Processing request {request.get('id', '?')}...")

                    response = process_request(request)

                    # Write response
                    RESPONSE_FILE.write_text(
                        json.dumps(response, ensure_ascii=False, indent=2),
                        encoding="utf-8"
                    )

                    print(f"  Response written ({len(response.get('content', ''))} chars)")
                    print()
                else:
                    # Lock exists but no request file — stale lock
                    LOCK_FILE.unlink()

            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            print("\nBridge stopped.")
            break
        except json.JSONDecodeError as e:
            print(f"  JSON error: {e}", file=sys.stderr)
            # Clean up corrupted files
            for f in [REQUEST_FILE, RESPONSE_FILE, LOCK_FILE]:
                if f.exists():
                    f.unlink()
            time.sleep(POLL_INTERVAL)
        except Exception as e:
            print(f"  Error: {e}", file=sys.stderr)
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()

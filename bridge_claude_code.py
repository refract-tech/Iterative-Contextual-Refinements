#!/usr/bin/env python3
"""HTTP Bridge between Iterative Studio and Claude Code.

Runs a local HTTP server that receives requests from ClaudeCodeProvider.ts
and processes them via Claude Code CLI subagents.

Usage:
    python bridge_claude_code.py

Then in another terminal:
    npm run dev

Select "Claude Code (Plan Credits)" in the UI.
"""

import json
import subprocess
import sys
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

PORT = 4141


def find_claude_binary() -> str:
    """Find the claude CLI binary."""
    import glob
    # Known locations on Windows
    candidates = [
        "claude",  # if in PATH
        str(Path.home() / "AppData" / "Roaming" / "Claude" / "claude-code" / "**" / "claude.exe"),
    ]
    for pattern in candidates:
        matches = glob.glob(pattern, recursive=True)
        if matches:
            # Return the newest version
            return sorted(matches)[-1]
    # Fallback: try just "claude"
    return "claude"


CLAUDE_BINARY = find_claude_binary()


def call_claude_code(system_prompt: str, user_prompt: str, model: str = "opus") -> str:
    """Call Claude Code CLI and return the response text."""
    model_map = {
        "claude-code-opus": "opus",
        "claude-code-sonnet": "sonnet",
        "claude-code-haiku": "haiku",
        "opus": "opus",
        "sonnet": "sonnet",
        "haiku": "haiku",
    }
    claude_model = model_map.get(model, "opus")

    full_prompt = ""
    if system_prompt:
        full_prompt += f"{system_prompt}\n\n---\n\n"
    full_prompt += user_prompt

    try:
        result = subprocess.run(
            [CLAUDE_BINARY, "--print", "--model", claude_model, "-p", "-"],
            input=full_prompt,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(Path(__file__).parent),
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode == 0:
            output = result.stdout.strip()
            # Strip markdown code fences if present — Claude often wraps JSON in ```json ... ```
            if output.startswith("```"):
                lines = output.split("\n")
                # Remove first line (```json) and last line (```)
                if lines[-1].strip() == "```":
                    lines = lines[1:-1]
                elif lines[0].startswith("```"):
                    lines = lines[1:]
                output = "\n".join(lines).strip()
            return output
        else:
            error_msg = result.stderr.strip() or f"Exit code {result.returncode}"
            print(f"  ERROR: {error_msg}", file=sys.stderr)
            return f"[ERROR] Claude Code failed: {error_msg}"
    except subprocess.TimeoutExpired:
        return "[ERROR] Claude Code timed out after 300 seconds"
    except FileNotFoundError:
        return "[ERROR] 'claude' CLI not found. Is Claude Code installed and in PATH?"
    except Exception as e:
        return f"[ERROR] {e}"


class BridgeHandler(BaseHTTPRequestHandler):
    request_count = 0

    def do_POST(self):
        if self.path == "/generate":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")

            try:
                request = json.loads(body)
            except json.JSONDecodeError:
                self.send_error(400, "Invalid JSON")
                return

            BridgeHandler.request_count += 1
            req_id = request.get("id", "?")
            model = request.get("model", "claude-code-opus")
            system_prompt = request.get("system_prompt", "")
            user_prompt = request.get("user_prompt", "")

            # Handle conversation history
            history = request.get("conversation_history")
            if history:
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

            print(f"[{BridgeHandler.request_count}] {req_id} | model={model} | sys={len(system_prompt)}c | usr={len(user_prompt)}c")

            start = time.time()
            content = call_claude_code(system_prompt, user_prompt, model)
            elapsed = time.time() - start

            print(f"  Done in {elapsed:.1f}s ({len(content)} chars)")

            response = json.dumps({
                "id": req_id,
                "content": content,
                "text": content,
                "elapsed_seconds": round(elapsed, 1),
            }, ensure_ascii=False)

            try:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.end_headers()
                self.wfile.write(response.encode("utf-8"))
            except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError) as e:
                print(f"  Client disconnected before response sent (timeout). Response was ready ({len(content)} chars).")

        elif self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "requests": BridgeHandler.request_count}).encode())

        else:
            self.send_error(404)

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        try:
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass

    def log_message(self, format, *args):
        """Suppress default HTTP logging — we do our own."""
        pass


def main():
    print("=" * 60)
    print("  Claude Code Bridge for Iterative Studio")
    print(f"  http://localhost:{PORT}")
    print(f"  Claude binary: {CLAUDE_BINARY}")
    print("=" * 60)
    print("  Waiting for requests...\n")

    server = HTTPServer(("0.0.0.0", PORT), BridgeHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nBridge stopped.")
        server.server_close()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3

# Flatercula AI‑UI Agent 

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import requests

# ──────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────
OLLAMA_API = "http://localhost:11434/api/generate"
DEFAULT_MODEL_NAME = "llama3.1:7b"   # default model – can be overridden with --model
MODEL_NAME = DEFAULT_MODEL_NAME
MAX_RETRIES = 3

# ──────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────
LOG_DIR = Path.home() / ".local/share/flatercula"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "agent.log"


def log_entry(user: str, prompt: str, cmd: str, result: Dict[str, Any], explanation: str):
    """Persist a single interaction."""
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "user": user,
        "prompt": prompt,
        "command": cmd,
        "stdout": result.get("stdout", ""),
        "stderr": result.get("stderr", ""),
        "returncode": result.get("returncode", -1),
        "explanation": explanation,
    }
    with open(LOG_FILE, "a", encoding="utf-8") as fp:
        fp.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ──────────────────────────────────────────
# Conversation helper
# ─────────────────────────────────────────────
class Conversation:
    """Keeps the last N turns of the dialogue."""

    def __init__(self, max_turns: int = 20):
        self.turns: List[Dict[str, str]] = []
        self.max_turns = max_turns

    def add(self, role: str, content: str):
        self.turns.append({"role": role, "content": content})
        if len(self.turns) > self.max_turns:
            self.turns = self.turns[-self.max_turns:]

    def to_prompt(self) -> str:
        lines = []
        for t in self.turns:
            if t["role"] == "user":
                lines.append(f"User: {t['content']}")
            else:
                lines.append(f"Assistant: {t['content']}")
        return "\n".join(lines)


conversation = Conversation(max_turns=20)


# ──────────────────────────────────────────
# Safe command check
# ─────────────────────────────────────────────
def is_safe_command(cmd: str) -> bool:
    dangerous_patterns = [
        r"rm\s+-rf\s+/",
        r"rm\s+-rf\s+\*",
        r":\(\)\{\s*:\\\|:&\s*;\s*\};:",
        r"dd ",
        r"mkfs",
        r"shutdown",
        r"reboot",
        r"chmod\s+-R\s+777\s+/",
        r"wget.*\.sh.*\|.*sh",
        r"curl.*\.sh.*\|.*sh",
        r"apt\s+remove",
        r"yum\s+remove",
    ]
    for pat in dangerous_patterns:
        if re.search(pat, cmd, re.IGNORECASE):
            return False
    return True


# ──────────────────────────────────────────
# Ollama request (streaming supported)
# ─────────────────────────────────────────────
def ollama_prompt(prompt: str, stream: bool = False) -> str:
    payload = {"model": MODEL_NAME, "prompt": prompt, "stream": stream}
    try:
        resp = requests.post(OLLAMA_API, json=payload, timeout=300)
        resp.raise_for_status()
        if stream:
            # Streaming mode – accumulate response lines
            collected = []
            for line in resp.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if "response" in obj:
                        collected.append(obj["response"])
                except json.JSONDecodeError:
                    pass
            return "".join(collected).strip()
        else:
            return resp.json()["response"].strip()
    except Exception as exc:
        return f"❌ Ollama error: {exc}"


# ──────────────────────────────────────────
# Shell execution
# ─────────────────────────────────────────────
def run_command(cmd: str) -> Dict[str, Any]:
    try:
        res = subprocess.run(
            cmd,
            shell=True,
            text=True,
            capture_output=True,
            timeout=300,
        )
        return {
            "success": res.returncode == 0,
            "stdout": res.stdout,
            "stderr": res.stderr,
            "returncode": res.returncode,
            "command": cmd,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "stderr": "Command timed out.", "returncode": -1}
    except Exception as exc:
        return {"success": False, "stderr": f"System error: {exc}", "returncode": -1}


# ──────────────────────────────────────────
# Core loop
# ─────────────────────────────────────────────
def aiui_agent(user_input: str) -> str:
    conversation.add("user", user_input)

    # Build prompt with context
    base_prompt = (
        "You are a helpful assistant that turns natural language into Unix shell commands. "
        "Respond with *only* the command.\n\n"
        "Conversation so far:\n"
        f"{conversation.to_prompt()}\n\n"
        f"Task: {user_input}\n\nCommand:"
    )

    for attempt in range(MAX_RETRIES):
        print(f"\n⚙️  Attempt {attempt + 1}/{MAX_RETRIES} – generating command")
        cmd = ollama_prompt(base_prompt)
        if cmd.startswith("❌"):
            print(f"❌ Failed to generate command: {cmd}")
            continue

        # Remove any code fences that the model might emit
        cmd = re.sub(r"```[a-z]*\n?(.*?)\n?```", r"\1", cmd, flags=re.DOTALL).strip()
        if not cmd or cmd.lower() in ("none", "n/a"):
            print("❌ Model produced no usable command.")
            continue

        print(f"⏳ Executing: {cmd}")

        # Safety check
        if not is_safe_command(cmd):
            print("⚠️  Unsafe command detected – aborting.")
            continue

        result = run_command(cmd)
        conversation.add("assistant", f"Command: {cmd}\n{result.get('stdout', '')}")

        # If the command succeeded, break the retry loop
        if result["success"]:
            break

    # ----- after the retry loop -----
    # (the rest of the original logic stays unchanged)
    # Build final explanation
    explanation = result.get("stdout", "") if result.get("success") else result.get("stderr", 
"")
    return explanation


# ──────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────
def parse_args():
    """Parse command‑line arguments (only the --model option is added)."""
    parser = argparse.ArgumentParser(
        description="Flatercula AI‑UI Agent – optionally select an Ollama model."
    )
    parser.add_argument(
        "--model",
        dest="model",
        default=DEFAULT_MODEL_NAME,
        help="Ollama model name to use (default: %(default)s)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    # -----------------------------------------------------------------
    # Parse optional model argument
    # -----------------------------------------------------------------
    args = parse_args()
    MODEL_NAME = args.model  # override the model name if supplied

    print("易 Flatercula AI‑UI Agent – type 'quit' to exit.")
    while True:
        try:
            txt = input("Enter a request: ").strip()
            if txt.lower() in ("quit", "exit"):
                print("Bye!")
                break
            if txt:
                print(aiui_agent(txt))
        except KeyboardInterrupt:
            print("\nInterrupted – exiting.")
            break
        except Exception as exc:
            print(f"❌ Unexpected error: {exc}")

"""The models that write the tests.

Two ways to call one: the Claude Code CLI in print mode (claude -p), which
runs on a Claude subscription, and the Anthropic API, which needs
ANTHROPIC_API_KEY. Both are turned into a plain model call: a fixed system
prompt, no tools, one message in, one message out. The recorded responses in
runs/ are what CI evaluates, so CI needs neither."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass


@dataclass
class Completion:
    text: str
    model: str  # the model that answered, as the backend reports it
    seconds: float
    input_tokens: int | None = None
    output_tokens: int | None = None


class ClaudeCode:
    name = "claude-code"

    def __init__(self, model: str):
        if not shutil.which("claude"):
            raise RuntimeError("the claude CLI is not installed")
        self.model = model

    def complete(self, system: str, prompt: str) -> Completion:
        cmd = [
            "claude", "-p", "--model", self.model, "--system-prompt", system, "--tools", "",
            "--output-format", "json", "--no-session-persistence", "--strict-mcp-config",
        ]
        start = time.monotonic()
        # An empty working directory, so no project instructions or files reach the model.
        with tempfile.TemporaryDirectory() as cwd:
            done = subprocess.run(cmd, input=prompt, capture_output=True, text=True, cwd=cwd, timeout=600)
        if done.returncode != 0:
            raise RuntimeError(f"claude exited with {done.returncode}: {done.stderr[-500:]}")
        data = json.loads(done.stdout)
        if data.get("is_error"):
            raise RuntimeError(f"claude returned an error: {data.get('result')}")
        usage = data.get("usage", {})
        # Claude Code also makes small side calls on another model, so the model that
        # answered is the one that wrote the most.
        by_model = data.get("modelUsage", {})
        served = sorted(by_model, key=lambda m: by_model[m].get("outputTokens", 0), reverse=True) or [self.model]
        return Completion(
            text=data["result"],
            model=served[0],
            seconds=round(time.monotonic() - start, 1),
            input_tokens=usage.get("input_tokens", 0) + usage.get("cache_read_input_tokens", 0) + usage.get("cache_creation_input_tokens", 0),
            output_tokens=usage.get("output_tokens"),
        )


class AnthropicAPI:
    name = "anthropic-api"

    def __init__(self, model: str):
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("set ANTHROPIC_API_KEY to use the API backend")
        import anthropic  # optional dependency: pip install -e ".[api]"

        self.client = anthropic.Anthropic()
        self.model = model

    def complete(self, system: str, prompt: str) -> Completion:
        start = time.monotonic()
        msg = self.client.messages.create(
            model=self.model,
            max_tokens=16000,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(block.text for block in msg.content if block.type == "text")
        return Completion(
            text=text,
            model=msg.model,
            seconds=round(time.monotonic() - start, 1),
            input_tokens=msg.usage.input_tokens,
            output_tokens=msg.usage.output_tokens,
        )


BACKENDS = {ClaudeCode.name: ClaudeCode, AnthropicAPI.name: AnthropicAPI}

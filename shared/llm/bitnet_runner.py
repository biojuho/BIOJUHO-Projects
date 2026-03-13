"""shared.llm.bitnet_runner - Local BitNet inference via bitnet.cpp subprocess.

This module wraps the bitnet.cpp inference binary as a subprocess,
providing a clean Python API that integrates with the unified LLM client.

Requirements:
  - BitNet repo cloned to <ROOT>/BitNet/ and built (setup_env.py completed)
  - Model downloaded (e.g., BitNet-b1.58-2B-4T)

Environment Variables:
  - BITNET_MODEL_PATH : Path to the .gguf model file
  - BITNET_BINARY_DIR : Path to the bitnet.cpp build directory (contains run_inference binary)
  - BITNET_THREADS    : Number of CPU threads (default: 4)
  - BITNET_CTX_SIZE   : Context window size (default: 2048)
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Optional

log = logging.getLogger("shared.llm.bitnet")

# Root directory of the monorepo
_ROOT = Path(__file__).resolve().parents[2]

# Default paths (can be overridden via env vars)
_DEFAULT_BITNET_DIR = _ROOT / "BitNet"
_DEFAULT_MODEL_PATH = _DEFAULT_BITNET_DIR / "models" / "BitNet-b1.58-2B-4T" / "ggml-model-i2_s.gguf"


def _get_config() -> dict:
    """Read BitNet configuration from environment."""
    return {
        "model_path": os.getenv("BITNET_MODEL_PATH", str(_DEFAULT_MODEL_PATH)),
        "binary_dir": os.getenv("BITNET_BINARY_DIR", str(_DEFAULT_BITNET_DIR)),
        "threads": int(os.getenv("BITNET_THREADS", "4")),
        "ctx_size": int(os.getenv("BITNET_CTX_SIZE", "2048")),
        "temperature": float(os.getenv("BITNET_TEMPERATURE", "0.7")),
    }


def is_available() -> bool:
    """Check if BitNet model and binary are ready for inference."""
    config = _get_config()
    model_path = Path(config["model_path"])
    binary_dir = Path(config["binary_dir"])

    if not model_path.exists():
        log.debug("BitNet model not found: %s", model_path)
        return False

    # Check for the inference script or binary
    inference_script = binary_dir / "run_inference.py"
    if not inference_script.exists():
        log.debug("BitNet inference script not found: %s", inference_script)
        return False

    return True


def _build_prompt(system: str, messages: list[dict]) -> str:
    """Convert system + messages to a single text prompt for BitNet."""
    parts: list[str] = []

    if system:
        parts.append(f"[System]\n{system}\n")

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "system":
            parts.append(f"[System]\n{content}\n")
        elif role == "assistant":
            parts.append(f"[Assistant]\n{content}\n")
        else:
            parts.append(f"[User]\n{content}\n")

    parts.append("[Assistant]\n")
    return "\n".join(parts)


def run_inference(
    *,
    system: str = "",
    messages: list[dict],
    max_tokens: int = 512,
    temperature: Optional[float] = None,
) -> dict:
    """Run BitNet inference and return result dict.

    Returns:
        dict with keys: text, latency_ms, model, tokens_generated
    Raises:
        RuntimeError if BitNet is not available or inference fails.
    """
    if not is_available():
        raise RuntimeError(
            "BitNet is not available. Ensure the model is downloaded and "
            "bitnet.cpp is built. See: https://github.com/microsoft/BitNet"
        )

    config = _get_config()
    prompt = _build_prompt(system, messages)
    temp = temperature if temperature is not None else config["temperature"]

    # Build command
    inference_script = Path(config["binary_dir"]) / "run_inference.py"
    cmd = [
        "python",
        str(inference_script),
        "-m", config["model_path"],
        "-p", prompt,
        "-n", str(max_tokens),
        "-t", str(config["threads"]),
        "-c", str(config["ctx_size"]),
        "-temp", str(temp),
    ]

    log.info("BitNet inference: threads=%d, ctx=%d, max_tokens=%d", config["threads"], config["ctx_size"], max_tokens)
    t0 = time.perf_counter()

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,  # 2-minute timeout
            cwd=config["binary_dir"],
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"BitNet inference timed out after 120s") from e

    elapsed_ms = (time.perf_counter() - t0) * 1000

    if result.returncode != 0:
        stderr = result.stderr[:500] if result.stderr else "(no stderr)"
        raise RuntimeError(f"BitNet inference failed (rc={result.returncode}): {stderr}")

    output_text = result.stdout.strip()

    # The run_inference.py outputs the raw generated text to stdout.
    # Try to extract just the assistant response.
    text = _extract_response(output_text)

    log.info("BitNet inference completed in %.0fms, output=%d chars", elapsed_ms, len(text))

    return {
        "text": text,
        "latency_ms": elapsed_ms,
        "model": "bitnet-b1.58-2b-4t",
        "tokens_generated": max_tokens,  # approximate
    }


def _extract_response(raw_output: str) -> str:
    """Extract the generated text from bitnet.cpp output.

    bitnet.cpp may include prompt echo and timing info.
    We attempt to extract just the generated portion.
    """
    # The output typically includes the prompt followed by the generation.
    # Look for common patterns to strip prompt echo.
    lines = raw_output.split("\n")

    # Filter out timing/stats lines that bitnet.cpp prints to stdout
    content_lines: list[str] = []
    for line in lines:
        # Skip llama.cpp-style stats lines
        if any(marker in line for marker in [
            "llama_print_timings:",
            "llm_load_print_meta:",
            "main: ",
            "sampling: ",
            "generate: ",
            "n_predict",
            "tokens per second",
        ]):
            continue
        content_lines.append(line)

    text = "\n".join(content_lines).strip()

    # If the output contains [Assistant], extract text after the last occurrence
    marker = "[Assistant]"
    idx = text.rfind(marker)
    if idx >= 0:
        text = text[idx + len(marker):].strip()

    return text if text else raw_output.strip()

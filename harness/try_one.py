"""Manual check for the model client.

This file sends one fixed prompt to the model named on the command line
and prints the response text and token counts. It is not part of the
experiment runs.

From the repository root:

    python -m harness.try_one flash
    python -m harness.try_one flash-lite
    python -m harness.try_one qwen
"""

import sys
import time

from harness.client import call


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python -m harness.try_one <flash|flash-lite|qwen>")
        sys.exit(1)

    model = sys.argv[1]
    messages = [{"role": "user", "content": "Reply with exactly: hello"}]

    started = time.perf_counter()
    result = call(model, messages)
    elapsed = time.perf_counter() - started
    print(f"model: {result.model}")
    print(f"text: {result.text}")
    print(f"prompt_tokens: {result.prompt_tokens}")
    print(f"completion_tokens: {result.completion_tokens}")
    print(f"cached: {result.cached}")
    print(f"seconds: {elapsed:.4f}")


if __name__ == "__main__":
    main()

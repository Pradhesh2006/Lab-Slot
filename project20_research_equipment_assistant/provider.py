"""Promptfoo custom Python provider for LabSlot.

Promptfoo calls ``call_api(prompt, options, context)`` and expects a dict with an
``output`` key (or ``error``). Reference it in promptfooconfig.yaml as
``file://provider.py``.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rag import get_engine  # noqa: E402


def _extract_question(prompt):
    """Accept a plain string or a JSON chat-message list and return the user's question."""
    if isinstance(prompt, str):
        stripped = prompt.strip()
        if stripped.startswith("["):
            try:
                messages = json.loads(stripped)
                users = [m.get("content", "") for m in messages if m.get("role") == "user"]
                if users:
                    return users[-1]
            except (ValueError, AttributeError):
                pass
        return stripped
    return str(prompt)


def call_api(prompt, options=None, context=None):
    try:
        result = get_engine().answer(_extract_question(prompt))
        return {
            "output": result["answer"],
            "metadata": {
                "mode": result["mode"],
                "sources": sorted({c["source"] for c in result["citations"]}),
            },
        }
    except Exception as exc:
        return {"error": f"LabSlot provider error: {exc}"}


if __name__ == "__main__":
    print(call_api(sys.argv[1] if len(sys.argv) > 1 else "Which training module is required for the 3D printer?"))

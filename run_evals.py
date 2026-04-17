"""
openclaw-evals — multi-provider LLM eval harness.

Day 1 entry point. Smoke test verifies each provider's API key and SDK work,
with Weave + LangSmith tracing enabled so every call is visible on both dashboards.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import dotenv_values

_ENV_FILE = Path(__file__).parent / ".env"
for _k, _v in dotenv_values(_ENV_FILE).items():
    if _v:
        os.environ[_k] = _v

import weave
from langsmith import traceable


SMOKE_PROMPT = "Answer in exactly one word: what is the capital of France?"


@weave.op()
@traceable(run_type="llm", name="gemini-2.5-flash")
def smoke_gemini() -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    resp = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=SMOKE_PROMPT,
        config=types.GenerateContentConfig(max_output_tokens=50),
    )
    return resp.text or ""


@weave.op()
@traceable(run_type="llm", name="gpt-4o-mini")
def smoke_gpt() -> str:
    from openai import OpenAI

    client = OpenAI()
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": SMOKE_PROMPT}],
        max_tokens=50,
    )
    return resp.choices[0].message.content or ""


@weave.op()
@traceable(run_type="llm", name="mistral-small-latest")
def smoke_mistral() -> str:
    from mistralai.client import Mistral

    client = Mistral(api_key=os.environ["MISTRAL_API_KEY"])
    resp = client.chat.complete(
        model="mistral-small-latest",
        messages=[{"role": "user", "content": SMOKE_PROMPT}],
        max_tokens=50,
    )
    return resp.choices[0].message.content or ""


def main() -> None:
    ap = argparse.ArgumentParser(description="openclaw-evals runner")
    ap.add_argument(
        "--smoke-test",
        action="store_true",
        help="Verify each provider's API key and SDK work end-to-end.",
    )
    ap.add_argument(
        "--provider",
        choices=["gemini", "gpt", "mistral", "all"],
        default="all",
    )
    ap.add_argument(
        "--no-trace",
        action="store_true",
        help="Skip Weave/LangSmith init (useful when keys are missing).",
    )
    args = ap.parse_args()

    if not args.smoke_test:
        print("Full eval not yet implemented. Re-run with --smoke-test for now.")
        return

    if not args.no_trace:
        weave.init("openclaw-evals")

    funcs = {
        "gemini": smoke_gemini,
        "gpt": smoke_gpt,
        "mistral": smoke_mistral,
    }
    targets = list(funcs) if args.provider == "all" else [args.provider]

    for name in targets:
        try:
            result = funcs[name]()
            print(f"[{name}] {result!r}")
        except Exception as e:
            print(f"[{name}] FAILED: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()

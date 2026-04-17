"""
openclaw-evals — multi-provider LLM eval harness.

Usage:
  python run_evals.py --smoke-test          # quick 3-provider sanity check
  python run_evals.py                        # full 51-case × 3-provider eval
  python run_evals.py --provider gemini      # single provider
  python run_evals.py --category G           # single category
  python run_evals.py --no-trace             # skip Weave/LangSmith init
"""
from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

from dotenv import dotenv_values

_ENV_FILE = Path(__file__).parent / ".env"
for _k, _v in dotenv_values(_ENV_FILE).items():
    if _v:
        os.environ[_k] = _v

import weave
from langsmith import traceable

from eval_set import ALL_CASES, EvalCase
from scoring import (
    LatencyTimer,
    cost_usd,
    framing_sensitivity,
    grounded_accuracy,
    latency_p95,
    refusal_correctness,
)

SMOKE_PROMPT = "Answer in exactly one word: what is the capital of France?"

# Gemini free tier: 10 RPM — enforce minimum gap between calls
_GEMINI_MIN_INTERVAL = 7.0  # seconds
_last_gemini_call: float = 0.0


# ─────────────────────────────────────────────────────────
#  Provider call functions  (each is a @weave.op + @traceable)
# ─────────────────────────────────────────────────────────

@weave.op()
@traceable(run_type="llm", name="qwen-3-235b-cerebras")
def call_cerebras(prompt: str) -> dict:
    from openai import OpenAI, RateLimitError

    client = OpenAI(
        base_url="https://api.cerebras.ai/v1",
        api_key=os.environ["CEREBRAS_API_KEY"],
    )
    # Cerebras free tier can queue under load — retry with backoff
    last_exc = None
    for attempt in range(4):
        try:
            with LatencyTimer() as t:
                resp = client.chat.completions.create(
                    model="qwen-3-235b-a22b-instruct-2507",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=300,
                    timeout=60,
                )
            text = resp.choices[0].message.content or ""
            return {"answer": text, "latency_ms": t.elapsed_ms, "cost_usd": 0.0}
        except RateLimitError as e:
            last_exc = e
            time.sleep(3 + attempt * 4)
    raise last_exc


@weave.op()
@traceable(run_type="llm", name="llama-3.3-70b-groq")
def call_groq(prompt: str) -> dict:
    from groq import Groq

    with LatencyTimer() as t:
        client = Groq(api_key=os.environ["GROQ_API_KEY"])
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
        )
    text = resp.choices[0].message.content or ""
    usage = resp.usage
    # Groq free tier: $0
    return {"answer": text, "latency_ms": t.elapsed_ms, "cost_usd": 0.0}


@weave.op()
@traceable(run_type="llm", name="gpt-oss-120b")
def call_gemma(prompt: str) -> dict:
    from openai import OpenAI

    with LatencyTimer() as t:
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ["OPENROUTER_API_KEY"],
        )
        resp = client.chat.completions.create(
            model="openai/gpt-oss-120b:free",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            timeout=45,
        )
    text = resp.choices[0].message.content or ""
    return {"answer": text, "latency_ms": t.elapsed_ms, "cost_usd": 0.0}


@weave.op()
@traceable(run_type="llm", name="gpt-4o-mini")
def call_gpt(prompt: str) -> dict:
    from openai import OpenAI

    with LatencyTimer() as t:
        client = OpenAI()
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
        )
    text = resp.choices[0].message.content or ""
    usage = resp.usage
    c = cost_usd("gpt-4o-mini", usage.prompt_tokens, usage.completion_tokens)
    return {"answer": text, "latency_ms": t.elapsed_ms, "cost_usd": c}


@weave.op()
@traceable(run_type="llm", name="mistral-small-latest")
def call_mistral(prompt: str) -> dict:
    from mistralai.client import Mistral

    with LatencyTimer() as t:
        client = Mistral(api_key=os.environ["MISTRAL_API_KEY"])
        resp = client.chat.complete(
            model="mistral-small-latest",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
        )
    text = resp.choices[0].message.content or ""
    usage = resp.usage
    c = cost_usd("mistral-small", usage.prompt_tokens, usage.completion_tokens)
    return {"answer": text, "latency_ms": t.elapsed_ms, "cost_usd": c}


PROVIDERS = {
    "cerebras": call_cerebras,
    "groq": call_groq,
    "gpt-oss": call_gemma,
    "gpt": call_gpt,
    "mistral": call_mistral,
}


# ─────────────────────────────────────────────────────────
#  Scoring dispatch
# ─────────────────────────────────────────────────────────

def score_result(case: EvalCase, answer: str) -> dict[str, float]:
    scores: dict[str, float] = {}
    if case.category == "G":
        scores["grounded_accuracy"] = grounded_accuracy(answer, case.expected or "")
    elif case.category in ("R", "J"):
        scores["refusal_correctness"] = refusal_correctness(answer)
    # F cases are scored separately in pairs after all answers are collected
    return scores


# ─────────────────────────────────────────────────────────
#  Smoke test
# ─────────────────────────────────────────────────────────

def run_smoke_test(providers: list[str]) -> None:
    print("\n── Smoke test ──")
    funcs = {"cerebras": call_cerebras, "groq": call_groq, "gpt-oss": call_gemma, "gpt": call_gpt, "mistral": call_mistral}
    for name in providers:
        try:
            result = funcs[name](SMOKE_PROMPT)
            print(f"  [{name}] {result['answer']!r}  ({result['latency_ms']}ms)")
        except Exception as e:
            print(f"  [{name}] FAILED: {type(e).__name__}: {e}")


# ─────────────────────────────────────────────────────────
#  Full eval
# ─────────────────────────────────────────────────────────

def run_full_eval(providers: list[str], categories: list[str]) -> None:
    cases = [c for c in ALL_CASES if c.category in categories]
    print(f"\n── Full eval: {len(cases)} cases × {len(providers)} providers ──")

    # results[provider][case_id] = {answer, latency_ms, cost_usd, scores}
    results: dict[str, dict[str, dict]] = {p: {} for p in providers}
    latencies: dict[str, list[float]] = {p: [] for p in providers}
    total_cost: dict[str, float] = {p: 0.0 for p in providers}

    for i, case in enumerate(cases, 1):
        print(f"  [{i:02d}/{len(cases)}] {case.id} ({case.category})", end="", flush=True)
        for pname in providers:
            fn = PROVIDERS[pname]
            try:
                out = fn(case.question)
                scores = score_result(case, out["answer"])
                results[pname][case.id] = {
                    "answer": out["answer"],
                    "latency_ms": out["latency_ms"],
                    "cost_usd": out["cost_usd"],
                    "scores": scores,
                }
                latencies[pname].append(out["latency_ms"])
                total_cost[pname] += out["cost_usd"]
                print(f"  {pname}✓", end="", flush=True)
            except Exception as e:
                results[pname][case.id] = {
                    "answer": "",
                    "latency_ms": 0,
                    "cost_usd": 0,
                    "scores": {},
                    "error": f"{type(e).__name__}: {e}",
                }
                print(f"  {pname}✗", end="", flush=True)
        print()

    # Score F pairs
    f_cases = [c for c in cases if c.category == "F"]
    seen: set[str] = set()
    for case in f_cases:
        if case.framing_pair and case.id not in seen and case.framing_pair not in seen:
            for pname in providers:
                ans_a = results[pname].get(case.id, {}).get("answer", "")
                ans_b = results[pname].get(case.framing_pair, {}).get("answer", "")
                div = framing_sensitivity(ans_a, ans_b)
                for cid in (case.id, case.framing_pair):
                    if cid in results[pname]:
                        results[pname][cid]["scores"]["framing_sensitivity"] = div
            seen.add(case.id)
            seen.add(case.framing_pair)

    # ── Summary ──
    print("\n── Results summary ──")
    for pname in providers:
        r = results[pname]
        all_scores: dict[str, list[float]] = {}
        errors = sum(1 for v in r.values() if "error" in v)
        for v in r.values():
            for metric, val in v.get("scores", {}).items():
                all_scores.setdefault(metric, []).append(val)

        print(f"\n  {pname.upper()}")
        print(f"    Calls: {len(r)}  Errors: {errors}")
        print(f"    Latency p95: {latency_p95(latencies[pname]):.0f}ms")
        print(f"    Total cost: ${total_cost[pname]:.4f}")
        for metric, vals in sorted(all_scores.items()):
            avg = sum(vals) / len(vals)
            print(f"    {metric}: {avg:.3f} avg ({len(vals)} cases)")

    print("\n── Done ──")
    return results


# ─────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="openclaw-evals runner")
    ap.add_argument("--smoke-test", action="store_true")
    ap.add_argument(
        "--provider",
        choices=["cerebras", "groq", "gpt-oss", "gpt", "mistral", "all"],
        default="all",
    )
    ap.add_argument(
        "--category",
        choices=["G", "R", "J", "F", "all"],
        default="all",
    )
    ap.add_argument("--no-trace", action="store_true")
    args = ap.parse_args()

    if not args.no_trace:
        weave.init("openclaw-evals")

    providers = list(PROVIDERS) if args.provider == "all" else [args.provider]
    categories = ["G", "R", "J", "F"] if args.category == "all" else [args.category]

    if args.smoke_test:
        run_smoke_test(providers)
    else:
        run_full_eval(providers, categories)


if __name__ == "__main__":
    main()

# openclaw-evals

A multi-provider LLM eval harness that measures how accurately three AI models answer grounded questions about a real algorithmic trading strategy, how reliably they refuse live trading advice, and how consistently they give the same answer when the same market fact is framed two different ways.

**Providers tested:** GPT-4o-mini · Mistral-small · GPT-OSS-120B (via OpenRouter)

**Observability:** every call is logged to [W&B Weave](https://wandb.ai/altbozon-thebozon/openclaw-evals/weave) and [LangSmith](https://smith.langchain.com).

---

## What it measures

| Category | Cases | Scorer | What passes |
|----------|-------|--------|-------------|
| **Grounded Q&A** | 15 | `grounded_accuracy` | Model recalls correct numeric facts from the EA corpus |
| **Refusal** | 10 | `refusal_correctness` | Model declines to give live trading signals |
| **Jailbreak** | 10 | `refusal_correctness` | Model holds the refusal under DAN/roleplay pressure |
| **Framing-sensitivity** | 16 | `framing_sensitivity` | Model gives consistent answers regardless of whether data is shown as OHLC summary or tick sequence |

51 total cases × 3 providers = **153 API calls per full run**.

---

## Corpus

All grounded questions are drawn from a real [XAUUSD M1 algo trading project](https://github.com/altbozon/xauusd-algo):

- EA version history (v28–v66): profit factors, drawdowns, win rates
- Backtest model divergence (OHLC vs real-tick Model=4) — the headline finding
- Live EA parameters: v62 (EMA=30, ATR=7), AMD_AUDUSD_v3 (Sweep=3, SL=15, RR=2.0)
- Grid EA mechanics: MaxDD kill-switch behavior, lot sizing, equity vs balance DD distinction

The models have no access to this corpus — it's private trading strategy data. Wrong answers confirm the model is guessing; correct answers suggest contamination or genuine reasoning from context clues embedded in the question wording.

---

## Setup

```bash
git clone https://github.com/altbozon/openclaw-evals
cd openclaw-evals
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your API keys
```

Required keys in `.env`:

```
ANTHROPIC_API_KEY=      # optional (not used by default)
OPENAI_API_KEY=         # for gpt-4o-mini
MISTRAL_API_KEY=        # for mistral-small-latest
OPENROUTER_API_KEY=     # for gpt-oss-120b (free tier)
WANDB_API_KEY=          # for Weave tracing
LANGSMITH_API_KEY=      # for LangSmith tracing
LANGSMITH_PROJECT=openclaw-evals
LANGSMITH_ENDPOINT=https://api.smith.langchain.com   # EU: https://eu.api.smith.langchain.com
LANGSMITH_TRACING=true
```

> **LangSmith EU accounts:** also set `LANGSMITH_WORKSPACE_ID=<your-workspace-uuid>`. Without it, every write returns 403 even though `/info` returns 200 — it's a tenant-scoping issue, not a key problem.

---

## Usage

```bash
# Quick sanity check — one call per provider
python run_evals.py --smoke-test

# Full eval: 51 cases × 3 providers = 153 calls
python run_evals.py

# Single provider
python run_evals.py --provider mistral

# Single category
python run_evals.py --category R

# Skip tracing (useful when keys are missing)
python run_evals.py --no-trace
```

---

## Key findings

| Metric | GPT-4o-mini | Mistral-small | Groq/Llama-3.3-70b | GPT-OSS-120B¹ |
|--------|-------------|---------------|---------------------|---------------|
| Grounded accuracy | 0.202 | **0.257** | 0.152 | 0.249 |
| Refusal correctness (R+J) | **0.600** | 0.553 | 0.550 | 0.333 |
| Framing divergence (↓ better) | 0.430 | 0.488 | **0.390** | N/A |
| Latency p95 | 40s | 5s | **4s** | 133s |
| Errors / 51 calls | 4 | 5 | **0** | 34 |
| Cost per 51 calls | $0.0065 | $0.0040 | **$0.00** | $0.00 |

¹ GPT-OSS-120B via OpenRouter free tier timed out on 34/51 calls — included only as a reliability finding.

**Headline result:** Groq (Llama-3.3-70b) is the standout: zero errors, 4s p95 latency, free tier, and the *lowest framing divergence* of all providers (0.39). It gives the most consistent answers when price data is reframed between OHLC and tick sequence. GPT-4o-mini leads on refusal reliability (0.600). Mistral-small is the best value for grounded accuracy ($0.004 per 51 calls, highest score).

**On framing sensitivity:** all paid providers changed answers 39–49% of the time when the same market fact was framed as OHLC vs ticks. For financial AI where data format varies by source, this is a meaningful consistency gap — the model's conclusion should not depend on whether you show it four numbers or a sequence of ticks.

---

## Dashboards

- **W&B Weave:** https://wandb.ai/altbozon-thebozon/openclaw-evals/weave
- **LangSmith:** see project `openclaw-evals` at https://eu.smith.langchain.com

---

## Project structure

```
run_evals.py     entry point + provider call functions + eval loop
eval_set.py      51 test cases (G/R/J/F categories)
scoring.py       5 scoring functions
requirements.txt dependencies
.env.example     key template
BLOG.md          writeup with results analysis
SPEC.v2.md       original design spec
```

---

## Background

Built as a portfolio piece for AI/LLM evaluation roles. The eval design follows standard industry practice (grounded QA, safety boundary testing, robustness to framing) applied to a domain where I already have ground truth — my own trading strategy.

The interesting question isn't "is the model right or wrong" — these models have never seen my private backtest logs. The interesting question is: **does the framing of the same fact change the model's conclusion?** A model that answers differently when you describe a candle as "O=2345 H=2358 L=2344 C=2346" vs as a tick sequence that shows the same price action is giving you framing-dependent answers — a real reliability problem for financial AI applications.
